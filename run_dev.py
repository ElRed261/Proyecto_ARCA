"""Corredor DEV de Neo Arca (no es producto, no va a packaging).

Flujo real F7.5: splash de restauración → LoginScreen → AppShell con rail.
Ejecutar con el venv GIL (PySide6 no corre en ft):

    .venv-gil/bin/python run_dev.py

Credenciales dev (fijas, SOLO desarrollo): admin@arca.rd / ArcaDev123!
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel

ROOT = Path(__file__).resolve().parent
DEV_DIR = ROOT / "dev"
DB_PATH = DEV_DIR / "neoarca-dev.db"

DEV_EMAIL = "admin@arca.rd"
DEV_PASSWORD = "ArcaDev123!"

sys.path.insert(0, str(ROOT))

from oms_core.db.connection import connect
from oms_core.db.migrations import migrate
from oms_core.db.repositories import users as users_repo
from oms_core.services import auth
from oms_ui.login_window import LoginWindow
from oms_ui.main_window import MainWindow
from oms_ui.startup import clear_token, save_token, try_restore_session
from oms_ui.theme import apply_theme


def ensure_dev_user(conn) -> None:
    if users_repo.get_user_by_email(conn, DEV_EMAIL) is None:
        auth.add_user(conn, DEV_EMAIL, auth.hash_password(DEV_PASSWORD), "admin")
    print(f"[dev] {DEV_EMAIL} / {DEV_PASSWORD}", flush=True)


def main() -> int:
    DEV_DIR.mkdir(exist_ok=True)
    conn = connect(DB_PATH)
    migrate(conn)
    ensure_dev_user(conn)

    app = QApplication([])
    family = apply_theme(app)
    print(f"[dev] fuente: {family or 'sistema (fallback)'}", flush=True)
    store = auth.SessionStore()

    splash = QLabel("Restaurando sesión…")
    splash.setWindowTitle("Neo Arca")
    splash.resize(1280, 800)
    splash.setAlignment(
        __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignCenter
    )
    splash.show()
    app.processEvents()
    restored = try_restore_session(store)
    splash.close()

    state: dict = {}

    def open_shell(session) -> None:
        save_token(session.access_token)
        shell = MainWindow(role=session.role, db_path=conn, email=session.user_email)
        shell.resize(1280, 800)
        shell.logout_requested.connect(lambda: (clear_token(), shell.close(), show_login()))
        shell.show()
        state["shell"] = shell
        print(f"[dev] sesión: {session.user_email} ({session.role})", flush=True)

    def show_login() -> None:
        state.pop("shell", None)
        login = LoginWindow(
            lambda email, password: auth.login(conn, store, email, password)
        )
        login.authenticated.connect(lambda session: (login.close(), open_shell(session)))
        login.show()
        state["login"] = login

    if restored is not None:
        open_shell(restored)
    else:
        show_login()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
