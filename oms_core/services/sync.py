"""Sync service — PRD F7: offline-first queue, backoff and dual emit.

Qt-free port (ADR-03) of the read-only oracle
``OLD/frontend/src-tauri/src/infrastructure/storage/sync_queue.rs``:

- ``enqueue`` (UNIQUE dedupe: one row per ``(module, station, path)``);
- ``get_sync_status`` (pending count + oldest pending + last error);
- ``retry_pending_sync(force=False)`` with the EXACT oracle backoff: a row
  with ``attempts > 0`` is skipped while
  ``now < last_attempt + min(2^attempts, 60) minutes``; ``force=True``
  (manual button) processes everything now; identical online content marks
  the row synced WITHOUT rewriting;
- ``emit_after_save`` / ``emit_dual_after_save`` (transport = copy to the
  online root; failures stay queued with ``last_error`` and NEVER raise to
  the UI).

F7 additions the oracle never had (all optional, all defaulting to the
oracle behaviour): an injectable ``clock`` (epoch-ms callable) so tests are
deterministic, an injectable ``transport`` (``(source, target) -> wrote``)
so tests never touch a real Drive mount, and cooperative ``on_progress`` /
``should_stop`` hooks so the QThread worker can report and stop.

Deliberate, documented deviation from the oracle: a failed ``emit`` records
``last_error`` (+ attempt timestamps, attempts untouched) on the queued row
so the maintenance panel can show it; the oracle only enqueued silently.
"""

from __future__ import annotations

import calendar
import hashlib
import os
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from oms_core import paths as paths_mod
from oms_core.db.repositories import sync as sync_repo

#: Epoch-ms clock: ``() -> int``. Production passes ``None`` (wall clock).
Clock = Callable[[], int]

#: Copy transport: ``(source, target) -> wrote``; raises on failure.
#: ``False`` means the target already holds the identical content.
Transport = Callable[[Path, Path], bool]

#: Progress hook: ``(done_rows, total_rows) -> None`` (GUI thread must only
#: be reached through the worker signals, never from here directly).
ProgressHook = Callable[[int, int], None]

#: Stop predicate polled between rows (the worker threads its stop flag in).
StopHook = Callable[[], bool]


@dataclass(frozen=True)
class SyncRow:
    module: str
    station_code: str
    relative_path: str
    source_path: str


@dataclass(frozen=True)
class SyncErrorRow:
    station_code: str
    relative_path: str
    detail: str


@dataclass(frozen=True)
class SyncStatus:
    pending: int
    synced: int
    oldest: str | None
    last_error: str | None
    last_attempt: str | None
    last_errors: list[SyncErrorRow]


@dataclass
class SyncOutcome:
    attempted: int = 0
    uploaded: int = 0
    marked_synced: int = 0
    last_error: str | None = None
    stopped: bool = False

    def to_dict(self) -> dict:
        return {
            "attempted": self.attempted,
            "uploaded": self.uploaded,
            "marked_synced": self.marked_synced,
            "last_error": self.last_error,
            "stopped": self.stopped,
        }


@dataclass(frozen=True)
class OnlineEmit:
    configured: bool
    saved_online: bool
    error: str | None = None


def _now_ms(clock: Clock | None) -> int:
    if clock is not None:
        return int(clock())
    return int(time.time() * 1000)


def backoff_window_ms(attempts: int) -> int:
    """``min(2^attempts, 60)`` minutes in milliseconds — the oracle schedule.

    The oracle clamps the shift at 59 to avoid ``i64`` overflow; here the
    shift clamps at 6 because ``2^6 = 64`` already exceeds the 60-minute cap,
    so every larger attempt count maps to exactly 60 minutes as well.
    """
    shift = min(max(int(attempts), 0), 6)
    return min(1 << shift, 60) * 60_000


def _sha256_of_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def enqueue(conn: sqlite3.Connection, row: SyncRow) -> bool:
    """Queue a file (INSERT OR IGNORE: consecutive saves never duplicate).

    Returns True when a new row was inserted, False when the
    ``(module, station, path)`` row already existed.
    """
    return sync_repo.enqueue_pending(
        conn,
        sync_repo.SyncRow(
            module=row.module,
            station_code=row.station_code,
            relative_path=row.relative_path,
            source_path=row.source_path,
        ),
        _sha256_of_file(Path(row.source_path)),
    )


def get_sync_status(conn: sqlite3.Connection) -> SyncStatus:
    """Aggregated queue state for the sync panel (P3.4 port, extended)."""
    base = sync_repo.get_sync_status(conn)
    oldest_row = conn.execute(
        "SELECT MIN(created_at) FROM sync_pending WHERE synced_at IS NULL"
    ).fetchone()
    oldest = oldest_row[0] if oldest_row else None
    error_row = conn.execute(
        "SELECT last_error FROM sync_pending"
        " WHERE synced_at IS NULL AND last_error IS NOT NULL"
        " ORDER BY last_attempt_at DESC LIMIT 1"
    ).fetchone()
    return SyncStatus(
        pending=base.pending,
        synced=base.synced,
        oldest=oldest,
        last_error=error_row[0] if error_row else None,
        last_attempt=base.last_attempt,
        last_errors=[
            SyncErrorRow(
                station_code=item.station_code,
                relative_path=item.relative_path,
                detail=item.detail,
            )
            for item in base.last_errors
        ],
    )


def copy_transport(source: Path, target: Path) -> bool:
    """Default transport: atomic file copy to the online root.

    Returns True when it wrote, False when the target already holds the
    identical content (sha match: mark synced WITHOUT rewriting, oracle
    P3.3). Raises with a plain message on any failure — the caller records
    it on the queued row instead of propagating it.
    """
    if not source.is_file():
        raise FileNotFoundError(f"source file is gone: {source}")
    payload = source.read_bytes()
    try:
        if target.is_file() and _sha256_of_file(target) == hashlib.sha256(payload).hexdigest():
            return False
    except OSError:
        pass  # unreadable target: fall through and overwrite it
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}")
    tmp.write_bytes(payload)
    os.replace(tmp, target)
    return True


def retry_pending_sync(
    conn: sqlite3.Connection,
    offline_root: str | Path,
    online_root: str | Path,
    force: bool = False,
    *,
    clock: Clock | None = None,
    transport: Transport | None = None,
    on_progress: ProgressHook | None = None,
    should_stop: StopHook | None = None,
) -> SyncOutcome:
    """One retry pass over the pending rows (oracle P3.3, cooperative).

    Never raises transport failures to the caller: each failing row stays
    queued with ``attempts + 1`` and its ``last_error`` set. Only a broken
    database itself propagates (nothing could be recorded anywhere then).
    """
    offline = Path(offline_root)
    online = Path(online_root)
    carry = transport or copy_transport
    now_ms = _now_ms(clock)

    rows = conn.execute(
        "SELECT module, station_code, relative_path, attempts, last_attempt_ms"
        " FROM sync_pending WHERE synced_at IS NULL ORDER BY created_at"
    ).fetchall()
    total = len(rows)
    done = 0
    outcome = SyncOutcome()

    for row in rows:
        module = row["module"]
        station_code = row["station_code"]
        relative_path = row["relative_path"]
        attempts = int(row["attempts"])
        last_ms = row["last_attempt_ms"]

        if should_stop is not None and should_stop():
            outcome.stopped = True
            break

        # Backoff, verbatim oracle gate: rows with attempts > 0 rest while
        # now < last_attempt + min(2^attempts, 60) minutes. force bypasses.
        if (
            not force
            and attempts > 0
            and last_ms is not None
            and now_ms - int(last_ms) < backoff_window_ms(attempts)
        ):
            done += 1
            if on_progress is not None:
                on_progress(done, total)
            continue

        outcome.attempted += 1
        try:
            wrote = carry(offline / relative_path, online / relative_path)
        except Exception as exc:  # noqa: BLE001 - recorded on the row by design
            detail = str(exc) or type(exc).__name__
            conn.execute(
                "UPDATE sync_pending SET attempts = ?, last_error = ?,"
                " last_attempt_ms = ?, last_attempt_at = CURRENT_TIMESTAMP"
                " WHERE module = ? AND station_code = ? AND relative_path = ?"
                " AND synced_at IS NULL",
                (attempts + 1, detail, now_ms, module, station_code, relative_path),
            )
            conn.commit()
            outcome.last_error = detail
        else:
            if wrote:
                outcome.uploaded += 1
            conn.execute(
                "UPDATE sync_pending SET synced_at = CURRENT_TIMESTAMP, attempts = 0,"
                " last_error = NULL, last_attempt_ms = ?"
                " WHERE module = ? AND station_code = ? AND relative_path = ?"
                " AND synced_at IS NULL",
                (now_ms, module, station_code, relative_path),
            )
            conn.commit()
            outcome.marked_synced += 1
        done += 1
        if on_progress is not None:
            on_progress(done, total)
    return outcome


def emit_after_save(
    conn: sqlite3.Connection,
    offline_root: str | Path | None,
    online_root: str | Path | None,
    module: str,
    station_code: str,
    year: str,
    month: str,
    filename: str,
    *,
    transport: Transport | None = None,
    clock: Clock | None = None,
) -> OnlineEmit:
    """Dual emit after a successful offline save (oracle P3.2, testable core).

    No online root configured -> honest no-op. Transport failure -> the file
    is queued (dedupe keeps consecutive saves to one row) with ``last_error``
    set, and the error travels in the return value, never as an exception.
    """
    if online_root is None or str(online_root) == "":
        return OnlineEmit(configured=False, saved_online=False, error=None)
    offline = Path(offline_root) if offline_root not in (None, "") else Path("")
    relative_path = f"{module}/{station_code}/{year}/{month}/{filename}"
    source = offline / relative_path
    target = Path(online_root) / relative_path
    carry = transport or copy_transport
    now_ms = _now_ms(clock)

    try:
        carry(source, target)
    except Exception as exc:  # noqa: BLE001 - queued with last_error by design
        detail = str(exc) or type(exc).__name__
        enqueue(
            conn,
            SyncRow(
                module=module,
                station_code=station_code,
                relative_path=relative_path,
                source_path=str(source),
            ),
        )
        conn.execute(
            "UPDATE sync_pending SET last_error = ?, last_attempt_ms = ?,"
            " last_attempt_at = CURRENT_TIMESTAMP"
            " WHERE module = ? AND station_code = ? AND relative_path = ?"
            " AND synced_at IS NULL",
            (detail, now_ms, module, station_code, relative_path),
        )
        conn.commit()
        return OnlineEmit(configured=True, saved_online=False, error=detail)

    conn.execute(
        "UPDATE sync_pending SET synced_at = CURRENT_TIMESTAMP, attempts = 0,"
        " last_error = NULL, last_attempt_ms = ?"
        " WHERE module = ? AND station_code = ? AND relative_path = ?"
        " AND synced_at IS NULL",
        (now_ms, module, station_code, relative_path),
    )
    conn.commit()
    return OnlineEmit(configured=True, saved_online=True, error=None)


def _normalize_station_code(code: str) -> str:
    """Filesystem station key: trimmed lowercase (oracle P1.5)."""
    return code.strip().lower()


def _parse_fecha(fecha: str) -> tuple[str, str, str]:
    """Split ``YYYY-MM-DD`` or ``DDMMYYYY`` into ``(year, month, day)``.

    Real calendar validation (leap years included); anything else raises
    ``ValueError`` with a plain message (the emit reports it, never raises).
    """
    year, month, day = "", "", ""
    if len(fecha) == 10 and fecha[4] == "-" and fecha[7] == "-":
        year, month, day = fecha[0:4], fecha[5:7], fecha[8:10]
    elif len(fecha) == 8:
        day, month, year = fecha[0:2], fecha[2:4], fecha[4:8]
    else:
        raise ValueError(f"invalid fecha format: '{fecha}' is not YYYY-MM-DD nor DDMMYYYY")
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        raise ValueError(f"fecha '{fecha}' must contain only digits")
    month_n, day_n = int(month), int(day)
    if not 1 <= month_n <= 12:
        raise ValueError(f"invalid month in fecha '{fecha}'")
    last_day = calendar.monthrange(int(year), month_n)[1]
    if not 1 <= day_n <= last_day:
        raise ValueError(f"invalid day in fecha '{fecha}'")
    return year, f"{month_n:02d}", f"{day_n:02d}"


def emit_dual_after_save(
    conn: sqlite3.Connection,
    module: str,
    station_code: str,
    fecha: str,
    *,
    env: dict[str, str] | None = None,
    default_root: str | None = None,
    transport: Transport | None = None,
    clock: Clock | None = None,
) -> OnlineEmit:
    """Tauri-glue port without Tauri: resolve roots, then dual-emit.

    Roots come from the PathProfile offline/online pair (env-managed or test
    mode via ``ARCA_BASE_DIR`` -> honest no-op, exactly like the oracle).
    Never blocks the save and never raises: every failure mode returns an
    ``OnlineEmit`` with ``error`` set.
    """
    env_map = os.environ if env is None else env
    if "ARCA_BASE_DIR" in env_map:
        return OnlineEmit(configured=False, saved_online=False, error=None)

    try:
        profile = paths_mod.get_path_profile(conn)
    except Exception as exc:  # noqa: BLE001 - corrupt config must not break a save
        return OnlineEmit(configured=False, saved_online=False, error=str(exc))

    resolved_default = (
        default_root if default_root is not None else str(paths_mod.default_documents_root())
    )
    offline = (
        profile.offline_root if profile is not None and profile.offline_root else resolved_default
    )
    online = profile.online_root if profile is not None and profile.online_root else None

    try:
        year, month, day = _parse_fecha(fecha)
    except ValueError as exc:
        return OnlineEmit(configured=online is not None, saved_online=False, error=str(exc))

    station_norm = _normalize_station_code(station_code)
    filename = f"{station_norm}{day}{month}{year}.json"
    return emit_after_save(
        conn,
        offline,
        online,
        module,
        station_norm,
        year,
        month,
        filename,
        transport=transport,
        clock=clock,
    )
