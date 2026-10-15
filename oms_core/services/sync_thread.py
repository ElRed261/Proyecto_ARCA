"""SyncWorker — QThread wrapper around the cooperative retry loop.

Architectural note (ADR-03 exception, documented): ``oms_core`` is Qt-free
except for THIS module, which holds zero logic and zero UI access — it only
opens its own SQLite connection, runs
:func:`oms_core.services.sync.retry_pending_sync` with progress/stop hooks,
and carries the outcome back through signals. All decisions (backoff,
dedupe, error recording) stay in the Qt-free service, so the logic remains
testable without a GUI and portable to any future frontend.

Threading contract:

- the worker NEVER touches widgets (results travel via ``progress`` /
  ``outcome`` signals only);
- it opens its OWN connection (SQLite connections cannot cross threads);
- :meth:`request_stop` is thread-safe and is polled between rows, so a slow
  sync can be cancelled without killing the thread;
- ``run`` never raises: even a broken database arrives as an ``outcome``
  dict with ``error`` set, never as an exception in the GUI thread.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from oms_core.db.connection import connect
from oms_core.services import sync as sync_service


class SyncWorker(QThread):
    """One retry pass in a worker thread. See module docstring."""

    #: ``(done_rows, total_rows)`` — emitted from the worker thread.
    progress = Signal(int, int)
    #: :meth:`SyncOutcome.to_dict` plus an optional ``error`` entry.
    outcome = Signal(dict)

    def __init__(
        self,
        db_path: str | Path,
        offline_root: str | Path,
        online_root: str | Path | None,
        force: bool = True,
        *,
        transport: sync_service.Transport | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._db_path = Path(db_path)
        self._offline_root = offline_root
        self._online_root = online_root
        self._force = force
        self._transport = transport
        self._stop = threading.Event()

    def request_stop(self) -> None:
        """Ask the running pass to stop after the current row (thread-safe)."""
        self._stop.set()

    def run(self) -> None:
        try:
            if self._online_root is None or str(self._online_root) == "":
                self.outcome.emit(
                    {
                        "attempted": 0,
                        "uploaded": 0,
                        "marked_synced": 0,
                        "last_error": None,
                        "stopped": self._stop.is_set(),
                        "error": "no online root configured",
                    }
                )
                return
            conn = connect(self._db_path)
            try:
                result = sync_service.retry_pending_sync(
                    conn,
                    self._offline_root,
                    self._online_root,
                    force=self._force,
                    transport=self._transport,
                    on_progress=lambda done, total: self.progress.emit(done, total),
                    should_stop=self._stop.is_set,
                )
            finally:
                conn.close()
            self.outcome.emit(result.to_dict())
        except Exception as exc:  # noqa: BLE001 - never raise into the GUI thread
            self.outcome.emit(
                {
                    "attempted": 0,
                    "uploaded": 0,
                    "marked_synced": 0,
                    "last_error": str(exc) or type(exc).__name__,
                    "stopped": self._stop.is_set(),
                    "error": str(exc) or type(exc).__name__,
                }
            )
