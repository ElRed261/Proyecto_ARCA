"""Oracle run F7 (PRD section 7-F7): simulated failing root.

1. Backoff schedule: for attempts 1..7 a queued row is probed just INSIDE
   its ``min(2^attempts, 60)``-minute window (must skip) and just OUTSIDE
   (must attempt) with a deterministic clock.
2. Failing root then drains: a scripted transport fails twice, the clock
   walks past the 2- and 4-minute windows, the third pass heals and drains.
3. Responsiveness: a 25 x 512 KiB sync runs in a real QThread while an
   interval-0 timer counts event-loop ticks (no sleeps anywhere).

Writes ``oracle_F7.json`` next to this script. Read-only vs OLD (it is only
imported as the behavior reference documented in NOTA.md); test data lives
in tmp dirs. Run: ``QT_QPA_PLATFORM=offscreen .venv-gil/bin/python
Migración/evidencias/F7/oracle_F7.py``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from oms_core.db import migrations
from oms_core.db.connection import connect
from oms_core.services import sync as sync_service
from oms_core.services.sync_thread import SyncWorker

T0 = 1_700_000_000_000


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> int:
        return self.now

    def advance_minutes(self, minutes: float) -> None:
        self.now += int(minutes * 60_000)


def fresh_db(path: Path) -> sqlite3.Connection:
    conn = connect(path)
    migrations.migrate(conn)
    return conn


def seed_row(conn: sqlite3.Connection, offline: Path, name: str, payload: bytes) -> str:
    relative = f"synop/78485/2025/12/{name}"
    source = offline / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    sync_service.enqueue(conn, sync_service.SyncRow("synop", "78485", relative, str(source)))
    return relative


def set_attempts(
    conn: sqlite3.Connection, relative: str, attempts: int, last_ms: int | None
) -> None:
    conn.execute(
        "UPDATE sync_pending SET attempts = ?, last_attempt_ms = ?,"
        " last_attempt_at = CURRENT_TIMESTAMP WHERE relative_path = ?",
        (attempts, last_ms, relative),
    )
    conn.commit()


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="oracle_f7_"))
    conn = fresh_db(tmp / "o.db")
    offline = tmp / "off"
    online = tmp / "on"
    clock = Clock()
    calls: list[str] = []

    def ok_transport(source: Path, target: Path) -> bool:
        calls.append(str(source))
        return sync_service.copy_transport(source, target)

    # ---- 1. schedule boundaries -------------------------------------
    windows = {1: 2, 2: 4, 3: 8, 4: 16, 5: 32, 6: 60, 7: 60}
    schedule_checks = []
    schedule_ok = True
    for attempts, window in windows.items():
        relative = seed_row(conn, offline, f"sched-{attempts}.json", b"x")
        set_attempts(conn, relative, attempts, clock.now - (window * 60_000 - 30_000))
        before = len(calls)
        outcome = sync_service.retry_pending_sync(
            conn, offline, online, clock=clock, transport=ok_transport
        )
        skipped_inside = len(calls) == before and outcome.attempted == 0
        clock.advance_minutes(1)  # now past the window edge
        outcome = sync_service.retry_pending_sync(
            conn, offline, online, clock=clock, transport=ok_transport
        )
        ran_outside = len(calls) == before + 1 and outcome.marked_synced == 1
        ok = skipped_inside and ran_outside
        schedule_ok = schedule_ok and ok
        schedule_checks.append(
            {
                "attempts": attempts,
                "window_min": window,
                "skip_inside": skipped_inside,
                "run_outside": ran_outside,
                "ok": ok,
            }
        )

    # ---- 2. failing root then drains ---------------------------------
    failures = {"n": 0}

    def flaky(source: Path, target: Path) -> bool:
        failures["n"] += 1
        if failures["n"] <= 2:
            raise OSError(f"outage #{failures['n']}")
        return sync_service.copy_transport(source, target)

    relative = seed_row(conn, offline, "drain.json", b"drain-me")
    first = sync_service.retry_pending_sync(conn, offline, online, clock=clock, transport=flaky)
    clock.advance_minutes(1)
    skipped = sync_service.retry_pending_sync(conn, offline, online, clock=clock, transport=flaky)
    clock.advance_minutes(2)
    second = sync_service.retry_pending_sync(conn, offline, online, clock=clock, transport=flaky)
    clock.advance_minutes(5)
    third = sync_service.retry_pending_sync(conn, offline, online, clock=clock, transport=flaky)
    status = sync_service.get_sync_status(conn)
    drain_ok = (
        (first.attempted, first.marked_synced, first.last_error) == (1, 0, "outage #1")
        and skipped.attempted == 0
        and second.last_error == "outage #2"
        and (third.attempted, third.uploaded, third.marked_synced) == (1, 1, 1)
        and (status.pending, status.synced) == (0, 8)
        and (online / relative).read_bytes() == b"drain-me"
    )

    # ---- 3. threaded responsiveness -----------------------------------
    _app = QApplication.instance() or QApplication([])  # kept alive for the loop
    tdir = tmp / "thread"
    tdir.mkdir(parents=True, exist_ok=True)
    toff, ton = tdir / "off", tdir / "on"
    tconn = fresh_db(tdir / "t.db")
    for i in range(25):
        seed_row(tconn, toff, f"t{i}.json", b"y" * 524288)
    tconn.close()
    ticks: list[int] = []
    ticker = QTimer()
    ticker.setInterval(0)
    ticker.timeout.connect(lambda: ticks.append(1))
    outcomes: list[dict] = []
    loop = QEventLoop()
    guard = QTimer()
    guard.setSingleShot(True)
    guard.setInterval(15000)
    guard.timeout.connect(loop.quit)
    worker = SyncWorker(tdir / "t.db", toff, ton, force=True)
    worker.outcome.connect(lambda d: (outcomes.append(d), loop.quit()))
    ticker.start()
    guard.start()
    started = time.monotonic()
    worker.start()
    loop.exec()
    elapsed_ms = (time.monotonic() - started) * 1000
    ticker.stop()
    guard.stop()
    worker.wait(5000)
    thread_ok = bool(outcomes) and outcomes[0].get("marked_synced") == 25 and len(ticks) > 0

    verdict = schedule_ok and drain_ok and thread_ok
    report = {
        "schedule_checks": schedule_checks,
        "schedule_ok": schedule_ok,
        "drain": {
            "first": first.to_dict(),
            "skipped_while_in_window": skipped.attempted == 0,
            "second_error": second.last_error,
            "third": third.to_dict(),
            "final_pending": status.pending,
            "final_synced": status.synced,
            "ok": drain_ok,
        },
        "thread": {
            "rows": 25,
            "payload_bytes_each": 524288,
            "event_ticks_during_op": len(ticks),
            "elapsed_ms": round(elapsed_ms, 1),
            "marked_synced": outcomes[0].get("marked_synced") if outcomes else None,
            "ok": thread_ok,
        },
        "verdict_ok": verdict,
    }
    out_path = Path(__file__).resolve().parent / "oracle_F7.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("verdict:", "ok" if verdict else "MISMATCH")
    if not verdict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
