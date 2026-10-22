"""F7 core — RED: sync service, backoff schedule, dual emit (Qt-free, ADR-03).

Ports the ``sync_queue.rs`` oracle surface (enqueue dedupe, backoff
``min(2^attempts, 60)`` minutes, emit-after-save) with an injectable clock
and transport so every timing assertion is deterministic.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from oms_core.services import sync as sync_service

T0 = 1_700_000_000_000  # fixed epoch-ms for the deterministic clock


class FakeClock:
    def __init__(self, now_ms: int = T0) -> None:
        self.now_ms = now_ms

    def __call__(self) -> int:
        return self.now_ms

    def advance_minutes(self, minutes: float) -> None:
        self.now_ms += int(minutes * 60_000)


class FakeTransport:
    """Scripted transport: fail ``fail_times`` calls, then copy for real."""

    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.calls: list[tuple[Path, Path]] = []

    def __call__(self, source: Path, target: Path) -> bool:
        self.calls.append((source, target))
        if len(self.calls) <= self.fail_times:
            raise OSError(f"simulated outage #{len(self.calls)}")
        return sync_service.copy_transport(source, target)


def _write_source(offline: Path, relative: str, payload: bytes = b"datum") -> Path:
    source = offline / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    return source


def _seed_row(
    conn: sqlite3.Connection,
    offline: Path,
    *,
    relative: str = "synop/78485/2025/12/f.json",
    attempts: int = 0,
    last_ago_minutes: float | None = None,
    clock: FakeClock | None = None,
) -> None:
    _write_source(offline, relative)
    sync_service.enqueue(
        conn,
        sync_service.SyncRow("synop", "78485", relative, str(offline / relative)),
    )
    last_ms = None
    if last_ago_minutes is not None:
        assert clock is not None
        last_ms = clock.now_ms - int(last_ago_minutes * 60_000)
    conn.execute(
        "UPDATE sync_pending SET attempts = ?, last_attempt_ms = ?,"
        " last_attempt_at = CURRENT_TIMESTAMP WHERE relative_path = ?",
        (attempts, last_ms, relative),
    )
    conn.commit()


# ------------------------------------------------------------------ enqueue


def test_enqueue_dedupes_like_the_oracle(fresh_db, tmp_path):
    offline = tmp_path / "off"
    source = _write_source(offline, "synop/78485/2025/12/f.json")
    row = sync_service.SyncRow("synop", "78485", "synop/78485/2025/12/f.json", str(source))

    assert sync_service.enqueue(fresh_db, row) is True
    assert sync_service.enqueue(fresh_db, row) is False
    assert sync_service.get_sync_status(fresh_db).pending == 1


# ------------------------------------------------------------------ backoff


@pytest.mark.parametrize(
    ("attempts", "window_minutes"),
    [(1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 60), (7, 60), (10, 60), (59, 60)],
)
def test_backoff_window_matches_oracle_schedule(fresh_db, tmp_path, attempts, window_minutes):
    assert sync_service.backoff_window_ms(attempts) == window_minutes * 60_000


@pytest.mark.parametrize(
    ("attempts", "window_minutes"),
    [(1, 2), (2, 4), (3, 8), (4, 16), (5, 32), (6, 60), (10, 60)],
)
def test_retry_skips_inside_window_and_runs_past_it(fresh_db, tmp_path, attempts, window_minutes):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    clock = FakeClock()

    # inside the window: skipped, attempt counter untouched
    _seed_row(
        fresh_db, offline, attempts=attempts, last_ago_minutes=window_minutes - 1, clock=clock
    )
    transport = FakeTransport()
    outcome = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert transport.calls == []
    assert outcome.attempted == 0
    row = fresh_db.execute("SELECT attempts FROM sync_pending").fetchone()
    assert row[0] == attempts

    # past the window: due
    clock.advance_minutes(2)
    outcome = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert len(transport.calls) == 1
    assert outcome.attempted == 1
    assert outcome.marked_synced == 1
    assert sync_service.get_sync_status(fresh_db).pending == 0


def test_retry_first_attempt_is_always_due(fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    clock = FakeClock()
    _seed_row(fresh_db, offline, attempts=0, last_ago_minutes=0, clock=clock)

    transport = FakeTransport()
    outcome = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert len(transport.calls) == 1
    assert outcome.marked_synced == 1


def test_retry_row_without_timestamp_is_due(fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    _seed_row(fresh_db, offline, attempts=3)  # last_attempt_ms NULL

    transport = FakeTransport()
    outcome = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=FakeClock(), transport=transport
    )
    assert len(transport.calls) == 1
    assert outcome.marked_synced == 1


def test_force_bypasses_the_backoff_window(fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    clock = FakeClock()
    _seed_row(fresh_db, offline, attempts=6, last_ago_minutes=0, clock=clock)

    transport = FakeTransport()
    outcome = sync_service.retry_pending_sync(
        fresh_db, offline, online, force=True, clock=clock, transport=transport
    )
    assert len(transport.calls) == 1
    assert outcome.marked_synced == 1


# --------------------------------------------------- failing root then drain


def test_failing_root_retries_then_drains_on_success(fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    clock = FakeClock()
    _write_source(offline, "synop/78485/2025/12/f.json")
    sync_service.enqueue(
        fresh_db,
        sync_service.SyncRow("synop", "78485", "synop/78485/2025/12/f.json", str(offline / "x")),
    )
    transport = FakeTransport(fail_times=2)

    first = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert (first.attempted, first.uploaded, first.marked_synced) == (1, 0, 0)
    assert first.last_error == "simulated outage #1"
    status = sync_service.get_sync_status(fresh_db)
    assert status.pending == 1
    assert status.last_error == "simulated outage #1"
    assert status.oldest is not None

    # attempts=1 -> 2-minute window: 1 minute later still skipped
    clock.advance_minutes(1)
    skipped = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert skipped.attempted == 0
    assert len(transport.calls) == 1

    # past the window: second failure, attempts=2 -> 4-minute window
    clock.advance_minutes(2)
    second = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert second.last_error == "simulated outage #2"
    assert fresh_db.execute("SELECT attempts FROM sync_pending").fetchone()[0] == 2

    # past the 4-minute window: the transport heals and the queue drains
    clock.advance_minutes(5)
    third = sync_service.retry_pending_sync(
        fresh_db, offline, online, clock=clock, transport=transport
    )
    assert (third.attempted, third.uploaded, third.marked_synced) == (1, 1, 1)
    assert (online / "synop/78485/2025/12/f.json").read_bytes() == b"datum"
    status = sync_service.get_sync_status(fresh_db)
    assert (status.pending, status.synced) == (0, 1)


def test_identical_online_content_marks_synced_without_rewrite(fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    _write_source(offline, "synop/78485/2025/12/f.json", b"same")
    _write_source(online, "synop/78485/2025/12/f.json", b"same")
    target = online / "synop/78485/2025/12/f.json"
    before = target.stat().st_mtime_ns
    sync_service.enqueue(
        fresh_db,
        sync_service.SyncRow("synop", "78485", "synop/78485/2025/12/f.json", str(offline / "x")),
    )

    outcome = sync_service.retry_pending_sync(fresh_db, offline, online)
    assert (outcome.attempted, outcome.uploaded, outcome.marked_synced) == (1, 0, 1)
    assert target.stat().st_mtime_ns == before
    assert sync_service.get_sync_status(fresh_db).pending == 0


def test_missing_source_is_recorded_never_raised(fresh_db, tmp_path):
    offline = tmp_path / "off"
    offline.mkdir()
    sync_service.enqueue(
        fresh_db,
        sync_service.SyncRow("synop", "78485", "synop/78485/2025/12/gone.json", str(offline / "x")),
    )

    outcome = sync_service.retry_pending_sync(fresh_db, offline, tmp_path / "on")
    assert outcome.attempted == 1
    assert outcome.marked_synced == 0
    assert outcome.last_error is not None
    assert sync_service.get_sync_status(fresh_db).pending == 1


def test_retry_reports_progress_and_honours_stop(fresh_db, tmp_path):
    offline = tmp_path / "off"
    for i in range(4):
        _write_source(offline, f"synop/78485/2025/12/f{i}.json")
        sync_service.enqueue(
            fresh_db,
            sync_service.SyncRow(
                "synop", "78485", f"synop/78485/2025/12/f{i}.json", str(offline / "x")
            ),
        )
    seen: list[tuple[int, int]] = []
    stop_after_two = {"n": 0}

    def transport(source, target):
        stop_after_two["n"] += 1
        return sync_service.copy_transport(source, target)

    outcome = sync_service.retry_pending_sync(
        fresh_db,
        offline,
        tmp_path / "on",
        transport=transport,
        on_progress=lambda done, total: seen.append((done, total)),
        should_stop=lambda: stop_after_two["n"] >= 2,
    )
    assert outcome.stopped is True
    assert outcome.attempted == 2
    assert seen[-1] == (2, 4)
    assert sync_service.get_sync_status(fresh_db).pending == 2


# ------------------------------------------------------------- emit paths


def test_emit_after_save_without_online_root_is_honest_noop(fresh_db, tmp_path):
    offline = tmp_path / "off"
    _write_source(offline, "synop/78485/2025/12/7848508122025.json")
    emit = sync_service.emit_after_save(
        fresh_db, offline, None, "synop", "78485", "2025", "12", "7848508122025.json"
    )
    assert emit == sync_service.OnlineEmit(configured=False, saved_online=False, error=None)
    assert sync_service.get_sync_status(fresh_db).pending == 0


def test_emit_after_save_copies_and_clears_queue(fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    _write_source(offline, "synop/78485/2025/12/7848508122025.json", b"hour-data")
    sync_service.enqueue(
        fresh_db,
        sync_service.SyncRow(
            "synop", "78485", "synop/78485/2025/12/7848508122025.json", str(offline / "x")
        ),
    )

    emit = sync_service.emit_after_save(
        fresh_db, offline, online, "synop", "78485", "2025", "12", "7848508122025.json"
    )
    assert emit.configured is True and emit.saved_online is True and emit.error is None
    assert (online / "synop/78485/2025/12/7848508122025.json").read_bytes() == b"hour-data"
    assert sync_service.get_sync_status(fresh_db).pending == 0


def test_emit_after_save_failure_stays_queued_with_error(fresh_db, tmp_path):
    offline = tmp_path / "off"
    offline.mkdir()

    def broken(source, target):
        raise OSError("drive asleep")

    emit = sync_service.emit_after_save(
        fresh_db,
        offline,
        tmp_path / "on",
        "synop",
        "78485",
        "2025",
        "12",
        "7848508122025.json",
        transport=broken,
    )
    assert emit.configured is True and emit.saved_online is False
    assert emit.error == "drive asleep"
    status = sync_service.get_sync_status(fresh_db)
    assert status.pending == 1
    assert status.last_error == "drive asleep"


def test_emit_dual_after_save_resolves_profile_roots(fresh_db, tmp_path):
    from oms_core import paths as paths_mod

    offline_base = tmp_path / "base-off"
    online_base = tmp_path / "base-on"
    paths_mod.set_path_profile(
        fresh_db,
        paths_mod.PathProfile(offline_root=str(offline_base), online_root=str(online_base)),
    )
    source = offline_base / "synop/78485/2025/12/7848508122025.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"dual")

    emit = sync_service.emit_dual_after_save(fresh_db, "synop", "78485", "08122025", env={})
    assert emit.configured is True and emit.saved_online is True
    assert (online_base / "synop/78485/2025/12/7848508122025.json").read_bytes() == b"dual"


def test_emit_dual_after_save_managed_env_is_noop(fresh_db, tmp_path):
    emit = sync_service.emit_dual_after_save(
        fresh_db, "synop", "78485", "08122025", env={"ARCA_BASE_DIR": str(tmp_path)}
    )
    assert emit == sync_service.OnlineEmit(configured=False, saved_online=False, error=None)


def test_emit_dual_after_save_rejects_bad_fecha(fresh_db):
    emit = sync_service.emit_dual_after_save(fresh_db, "synop", "78485", "32052025", env={})
    assert emit.saved_online is False
    assert emit.error is not None


def test_status_oldest_tracks_oldest_pending(fresh_db, tmp_path):
    offline = tmp_path / "off"
    _write_source(offline, "synop/78485/2025/12/a.json")
    _write_source(offline, "synop/78485/2025/12/b.json")
    sync_service.enqueue(
        fresh_db,
        sync_service.SyncRow("synop", "78485", "synop/78485/2025/12/a.json", "s"),
    )
    sync_service.enqueue(
        fresh_db,
        sync_service.SyncRow("synop", "78485", "synop/78485/2025/12/b.json", "s"),
    )
    status = sync_service.get_sync_status(fresh_db)
    assert status.pending == 2
    assert status.oldest is not None
    assert status.last_error is None
    assert status.last_errors == []


def test_backoff_never_exceeds_sixty_minutes():
    for attempts in (6, 7, 20, 59, 10_000):
        assert sync_service.backoff_window_ms(attempts) == 60 * 60_000


def test_backoff_rejects_nonsense_attempts_gracefully():
    assert sync_service.backoff_window_ms(-3) == 1 * 60_000
    assert sync_service.backoff_window_ms(0) == 1 * 60_000


def test_env_override_is_visible_to_dual_emit(fresh_db, tmp_path, monkeypatch):
    monkeypatch.setenv("ARCA_BASE_DIR", str(tmp_path))
    emit = sync_service.emit_dual_after_save(fresh_db, "synop", "78485", "08122025")
    assert emit.configured is False
    assert os.environ["ARCA_BASE_DIR"] == str(tmp_path)
