"""MaintenancePage — paths, sync panel and legacy migration (PRD F7).

PySide6 port of ``OLD/frontend/src/features/maintenance/pages/
MaintenancePage.jsx`` backed by the Qt-free ``oms_core.services.sync``
service (ADR-03: only presentation here):

- PathCards for the PathProfile roots (offline / online / summaries) with an
  honest writability probe each (``✓ carpeta escribible`` /
  ``✗ no escribible: <detail>`` — oracle strings verbatim), plus the backups
  retention card (``backups_max_age_days`` is a number, not a path, so it
  gets a spin box instead of a probe);
- sync panel (pending count, last error, retry-now through the QThread
  worker with progress, never blocking the event loop);
- legacy-migration button running the F6 one-shot migrate on the configured
  synop base, admin-gated through ``access.py`` (the service enforces it
  again with the exact oracle message).

Editing (paths save + migration) is admin-only; the sync panel is visible
to every role, exactly like the oracle.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from oms_core import paths as paths_mod
from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_core.services import sync as sync_service
from oms_core.services.sync_thread import SyncWorker
from oms_ui import theme as theme_mod

#: Retention choices for the backups card (0 = not set).
_BACKUPS_MAX_DAYS = 3650


@dataclass(frozen=True)
class ProbeResult:
    writable: bool
    error: str | None = None


def probe_path(path_str: str) -> ProbeResult:
    """Honest writability probe — port of Rust ``probe_path_path``.

    Creates the directory when missing, then writes/reads/deletes a probe
    file. Any failure returns ``writable=False`` with the concrete detail;
    success is only reported after the round-trip actually worked.
    """
    if not path_str or not path_str.strip():
        return ProbeResult(False, "empty path: choose a folder first")
    path = Path(path_str)
    if path.name == "":
        return ProbeResult(False, "invalid path: must point to a directory, not a drive root")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ProbeResult(False, f"could not create directory '{path}': {exc}")
    if not path.is_dir():
        return ProbeResult(False, f"'{path}' exists but is not a directory")
    probe_file = path / f".arca_probe_{os.getpid()}"
    try:
        probe_file.write_text("ok", encoding="utf-8")
    except OSError as exc:
        return ProbeResult(False, f"cannot write in '{path}': {exc}")
    try:
        content = probe_file.read_text(encoding="utf-8")
    except OSError as exc:
        return ProbeResult(False, f"cannot read back the probe in '{path}': {exc}")
    finally:
        try:
            probe_file.unlink()
        except OSError:
            pass
    if content != "ok":
        return ProbeResult(False, f"odd probe in '{path}': unexpected content")
    return ProbeResult(True)


def db_path_of(conn: sqlite3.Connection, explicit: str | Path | None = None) -> Path | None:
    """Resolve the database file behind ``conn`` (the worker needs its own).

    Uses ``PRAGMA database_list`` so pages built with a bare connection
    (tests, MainWindow) still find the file; ``None`` for memory databases.
    """
    if explicit is not None:
        return Path(explicit)
    try:
        rows = conn.execute("PRAGMA database_list").fetchall()
    except Exception:  # noqa: BLE001 - best effort only, missing file is valid
        return None
    for _seq, name, filename in rows:
        if name == "main" and filename:
            return Path(filename)
    return None


class PathCard(QGroupBox):
    """One editable root with probe + explore buttons (oracle PathCard)."""

    def __init__(self, title: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.field_name = ""
        layout = QVBoxLayout(self)
        self.hint_label = QLabel(hint)
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("/ruta/de/guardado")
        layout.addWidget(self.edit)
        row = QHBoxLayout()
        self.probe_button = QPushButton("Probar")
        self.probe_button.clicked.connect(self.run_probe)
        self.explore_button = QPushButton("Explorar")
        self.explore_button.clicked.connect(self.explore)
        self.result_label = QLabel("")
        self.result_label.setTextFormat(Qt.RichText)
        row.addWidget(self.probe_button)
        row.addWidget(self.explore_button)
        row.addWidget(self.result_label, 1)
        layout.addLayout(row)

    def run_probe(self) -> ProbeResult:
        result = probe_path(self.edit.text())
        if result.writable:
            self.result_label.setText("✓ carpeta escribible")
        else:
            self.result_label.setText(f"✗ no escribible: {result.error or 'sin detalle'}")
        return result

    def explore(self) -> None:
        picked = QFileDialog.getExistingDirectory(self, "Elegir carpeta", self.edit.text())
        if picked:
            self.edit.setText(picked)
            self.run_probe()


class MaintenancePage(QWidget):
    """Paths configuration + sync status + legacy migration."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        role: str = "admin",
        db_path: str | Path | None = None,
        transport: sync_service.Transport | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.role = role
        self._db_path = db_path_of(conn, db_path)
        self._transport = transport
        self._worker: SyncWorker | None = None
        self.can_edit = access.can_access(role, "admin")

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # ---- paths -----------------------------------------------------
        paths_box = QGroupBox("Rutas de guardado")
        paths_layout = QVBoxLayout(paths_box)
        self.cards: dict[str, PathCard] = {}
        for field_name, title, hint in (
            (
                "offline_root",
                "Raíz offline (local)",
                "Carpeta local donde viven las observaciones.",
            ),
            (
                "online_root",
                "Raíz online (Drive Desktop)",
                "Carpeta sincronizada. Sin ella, el dato queda offline y se reintenta.",
            ),
            (
                "summaries_dir",
                "Carpeta de resúmenes",
                "Opcional: carpeta aparte para el Resumen Mensual.",
            ),
        ):
            card = PathCard(title, hint)
            card.field_name = field_name
            card.edit.setEnabled(self.can_edit)
            card.probe_button.setEnabled(self.can_edit)
            card.explore_button.setEnabled(self.can_edit)
            self.cards[field_name] = card
            paths_layout.addWidget(card)

        paths_layout.addWidget(self._build_layout_box())

        backups_row = QHBoxLayout()
        backups_row.addWidget(QLabel("Backups: antigüedad máxima (días, 0 = sin definir)"))
        self.backups_spin = QSpinBox()
        self.backups_spin.setRange(0, _BACKUPS_MAX_DAYS)
        self.backups_spin.setEnabled(self.can_edit)
        backups_row.addWidget(self.backups_spin)
        paths_layout.addLayout(backups_row)

        if self.can_edit:
            self.save_button = QPushButton("Guardar configuración")
            self.save_button.clicked.connect(self.save_profile)
            paths_layout.addWidget(self.save_button)
        else:
            note = QLabel("Solo un administrador puede modificar las rutas.")
            paths_layout.addWidget(note)
            self.save_button = None
        self.save_label = QLabel("")
        paths_layout.addWidget(self.save_label)
        content_layout.addWidget(paths_box)

        # ---- apariencia (todos los roles) -------------------------------
        appearance_box = QGroupBox("Apariencia")
        appearance_layout = QHBoxLayout(appearance_box)
        appearance_layout.addWidget(QLabel("Tema"))
        self.theme_combo = QComboBox()
        for clave in theme_mod.THEMES:
            self.theme_combo.addItem(theme_mod.ETIQUETAS[clave], clave)
        actual = theme_mod.current_theme()
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(actual)))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_layout.addWidget(self.theme_combo)
        self.theme_label = QLabel(f"Activo: {theme_mod.ETIQUETAS[actual]}")
        appearance_layout.addWidget(self.theme_label)
        appearance_layout.addStretch(1)
        content_layout.addWidget(appearance_box)

        # ---- sync panel (every role) -----------------------------------
        sync_box = QGroupBox("Sincronización")
        sync_layout = QVBoxLayout(sync_box)
        self.pending_label = QLabel("Pendientes de enviar: …")
        sync_layout.addWidget(self.pending_label)
        self.last_error_label = QLabel("")
        self.last_error_label.setWordWrap(True)
        sync_layout.addWidget(self.last_error_label)
        self.error_list = QListWidget()
        self.error_list.setMaximumHeight(90)
        sync_layout.addWidget(self.error_list)
        retry_row = QHBoxLayout()
        self.retry_button = QPushButton("Reintentar ahora")
        self.retry_button.clicked.connect(self.retry_now)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        retry_row.addWidget(self.retry_button)
        retry_row.addWidget(self.progress_bar, 1)
        sync_layout.addLayout(retry_row)
        self.sync_status_label = QLabel("")
        self.sync_status_label.setWordWrap(True)
        sync_layout.addWidget(self.sync_status_label)
        content_layout.addWidget(sync_box)

        # ---- legacy migration (admin only) ------------------------------
        if self.can_edit:
            self.migrate_button = QPushButton("Migrar carpetas de meses legacy (one-shot)")
            self.migrate_button.clicked.connect(self.migrate_legacy)
            content_layout.addWidget(self.migrate_button)
            self.migrate_label = QLabel("")
            self.migrate_label.setWordWrap(True)
            content_layout.addWidget(self.migrate_label)
        else:
            self.migrate_button = None
            self.migrate_label = None

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self._load_profile()
        self.refresh_sync()

    # ------------------------------------------------------------------ paths

    def _load_profile(self) -> None:
        try:
            profile = paths_mod.get_path_profile(self.conn)
        except paths_mod.PathConfigError as exc:
            self.save_label.setText(f"No se pudo leer la configuración: {exc}")
            return
        if profile is None:
            return
        self.cards["offline_root"].edit.setText(profile.offline_root or "")
        self.cards["online_root"].edit.setText(profile.online_root or "")
        self.cards["summaries_dir"].edit.setText(profile.summaries_dir or "")
        self.backups_spin.setValue(profile.backups_max_age_days or 0)

    def current_profile(self) -> paths_mod.PathProfile:
        backups = self.backups_spin.value()
        return paths_mod.PathProfile(
            offline_root=self.cards["offline_root"].edit.text(),
            online_root=self.cards["online_root"].edit.text() or None,
            backups_max_age_days=backups if backups > 0 else None,
            summaries_dir=self.cards["summaries_dir"].edit.text() or None,
        )

    def _on_theme_changed(self, _index: int) -> None:
        """Cambia el tema en caliente y lo deja guardado (docs/DISENO_OMS.md §1)."""
        elegido = theme_mod.set_theme(str(self.theme_combo.currentData() or ""))
        app = QApplication.instance()
        if app is not None:
            theme_mod.apply_theme(app, elegido)
        self.theme_label.setText(f"Activo: {theme_mod.ETIQUETAS[elegido]}")

    def save_profile(self) -> bool:
        try:
            paths_mod.set_path_profile(self.conn, self.current_profile())
        except paths_mod.PathConfigError as exc:
            self.save_label.setText(f"No se pudo guardar: {exc}")
            return False
        self.save_label.setText("Configuración de rutas guardada")
        return True

    def _build_layout_box(self) -> QGroupBox:
        """Read-only view of the section tree created inside the root.

        The admin sees where each kind of file lands without having to open
        the folder; the tree is created automatically on startup.
        """
        box = QGroupBox("Estructura dentro de la raíz")
        rows = QVBoxLayout(box)
        for section, description in (
            ("synop", "observaciones sinópticas y CLI — <ESTACIÓN>/<AÑO>/<MES>/"),
            ("resumenes", "resúmenes mensuales — <ESTACIÓN>/<AÑO>/<MES>/"),
            ("exportaciones", "Excel y PDF exportados"),
            ("respaldos", "respaldos de base y JSON"),
        ):
            label = QLabel(f"{section}/ — {description}")
            label.setWordWrap(True)
            rows.addWidget(label)
        hint = QLabel(
            "Se crea sola bajo la raíz resuelta (por defecto "
            f"{paths_mod.default_documents_root()})."
        )
        hint.setWordWrap(True)
        rows.addWidget(hint)
        return box

    # ------------------------------------------------------------------ sync

    def _resolve_bases(self) -> tuple[str, str | None]:
        """Offline base + optional online base behind the current profile."""
        try:
            profile = paths_mod.get_path_profile(self.conn)
        except paths_mod.PathConfigError:
            profile = None
        default = str(paths_mod.default_documents_root())
        offline = profile.offline_root if profile and profile.offline_root else default
        online = profile.online_root if profile and profile.online_root else None
        return offline, online

    def refresh_sync(self) -> None:
        try:
            status = sync_service.get_sync_status(self.conn)
        except Exception as exc:  # noqa: BLE001 - panel must never break the page
            self.pending_label.setText("Pendientes de enviar: …")
            self.last_error_label.setText(f"No se pudo leer el estado: {exc}")
            return
        self.pending_label.setText(
            f"Pendientes de enviar: {status.pending} · Enviadas con éxito: {status.synced}"
        )
        self.last_error_label.setText(
            f"Último error: {status.last_error}" if status.last_error else ""
        )
        self.error_list.clear()
        self.error_list.addItems(
            f"{item.station_code} — {item.relative_path}: {item.detail}"
            for item in status.last_errors
        )

    def retry_now(self) -> None:
        # ALWAYS through the QThread worker: the event loop must stay alive
        # while the retry runs (PRD R3). ``transport`` is only a test hook
        # for deterministic runs without a Drive mount.
        if self._worker is not None and self._worker.isRunning():
            return
        if self._db_path is None:
            self.sync_status_label.setText("Reintento no disponible: base en memoria.")
            return
        offline, online = self._resolve_bases()
        if online is None:
            self.sync_status_label.setText("Sin raíz online configurada: nada que reintentar.")
            return
        self._worker = SyncWorker(
            self._db_path, offline, online, force=True, transport=self._transport
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.outcome.connect(self._on_outcome)
        self.retry_button.setEnabled(False)
        self.sync_status_label.setText("Sincronizando…")
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress_bar.setValue(int(100 * done / total) if total else 100)

    def _on_outcome(self, outcome: dict) -> None:
        self.retry_button.setEnabled(True)
        self.progress_bar.setValue(100)
        self._show_outcome(outcome)
        self.refresh_sync()
        self._worker = None

    def _show_outcome(self, outcome: dict) -> None:
        if outcome.get("error"):
            self.sync_status_label.setText(f"Fallo del reintento: {outcome['error']}")
        elif outcome.get("marked_synced", 0) > 0:
            self.sync_status_label.setText(f"Sincronizados: {outcome['marked_synced']}")
        elif outcome.get("last_error"):
            self.sync_status_label.setText(f"Sin éxito: {outcome['last_error']}")
        else:
            self.sync_status_label.setText("Nada pendiente por reintentar")

    # -------------------------------------------------------------- migration

    def _synop_base(self) -> Path:
        offline, _online = self._resolve_bases()
        return Path(offline) / "synop"

    def migrate_legacy(self) -> None:
        try:
            stats = audit_service.migrate_legacy_month_dirs(self._synop_base(), role=self.role)
        except PermissionError as exc:
            if self.migrate_label is not None:
                self.migrate_label.setText(f"No autorizado: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - report, never raise
            if self.migrate_label is not None:
                self.migrate_label.setText(f"No se pudo migrar: {exc}")
            return
        if self.migrate_label is not None:
            self.migrate_label.setText(
                f"Migración completa: {stats['renamed_dirs']} carpetas,"
                f" {stats['moved_files']} archivos"
            )
