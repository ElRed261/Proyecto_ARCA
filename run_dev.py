"""Corredor DEV de Neo Arca (no es producto, no va a packaging).

Abre la app de verdad en tu pantalla: login real contra BD dev
(./dev/neoarca-dev.db, migrada + usuario dev) y luego la ventana
sinóptica F4. Ejecutar con el venv GIL (PySide6 no corre en ft):

    .venv-gil/bin/python run_dev.py

Credenciales dev (fijas, SOLO desarrollo): admin@arca.rd / ArcaDev123!
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

ROOT = Path(__file__).resolve().parent
DEV_DIR = ROOT / "dev"
DB_PATH = DEV_DIR / "neoarca-dev.db"

DEV_EMAIL = "admin@arca.rd"
DEV_PASSWORD = "ArcaDev123!"

sys.path.insert(0, str(ROOT))

from oms_core.db.connection import connect  # noqa: E402
from oms_core.db.migrations import migrate  # noqa: E402
from oms_core.db.repositories import users as users_repo  # noqa: E402
from oms_core.services import auth  # noqa: E402
from oms_ui.login_dialog import LoginDialog  # noqa: E402
from oms_ui.pages.synoptic import SynopticWindow  # noqa: E402


def ensure_dev_user(conn) -> None:
    existing = users_repo.get_user_by_email(conn, DEV_EMAIL)
    if existing is None:
        auth.add_user(conn, DEV_EMAIL, auth.hash_password(DEV_PASSWORD), "admin")
        print(f"[dev] usuario creado: {DEV_EMAIL} / {DEV_PASSWORD}", flush=True)
    else:
        print(f"[dev] usuario existente: {DEV_EMAIL} / {DEV_PASSWORD}", flush=True)


def main() -> int:
    DEV_DIR.mkdir(exist_ok=True)
    conn = connect(DB_PATH)
    migrate(conn)
    ensure_dev_user(conn)

    app = QApplication([])
    store = auth.SessionStore()
    dialog = LoginDialog(
        lambda email, password: auth.login(conn, store, email, password)
    )
    if dialog.exec() != QDialog.Accepted:
        print("[dev] login cancelado", flush=True)
        return 0
    session = dialog.result_session
    print(f"[dev] sesión: {session.user_email} ({session.role})", flush=True)

    today = _dt.date.today().isoformat()
    window = SynopticWindow(conn, station="78485", fecha=today, config_dir=str(DEV_DIR))
    window.setWindowTitle(f"Neo Arca (dev) — Sinóptico {today}")
    window.resize(1280, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
