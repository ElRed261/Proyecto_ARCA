"""F3 — pytest-qt UI tests (QT_QPA_PLATFORM=offscreen, set in conftest.py).

Covers: LoginDialog success/failure with inline error, MainWindow nav
filtering per role, and the StationsAdminPage create round-trip."""

import pytest

from oms_core.db.connection import connect
from oms_core.db.migrations import migrate
from oms_core.db.repositories import stations as stations_repo
from oms_core.services import auth

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtWidgets import QDialog

from oms_ui.login_dialog import LoginDialog
from oms_ui.main_window import MainWindow
from oms_ui.pages.stations_admin import StationsAdminPage

PASSWORD = "Clave123!"


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "ui.db")
    migrate(conn)
    return conn


def add_user(conn, email, role):
    auth.add_user(conn, email, auth.hash_password(PASSWORD), role)
    return email


# ---------------------------------------------------------------- LoginDialog


def test_login_ok_acepta_y_guarda_sesion(qtbot, db):
    store = auth.SessionStore()
    add_user(db, "ui_admin@arca.test", "admin")

    dialog = LoginDialog(lambda email, password: auth.login(db, store, email, password))
    qtbot.addWidget(dialog)
    dialog.email_edit.setText("ui_admin@arca.test")
    dialog.password_edit.setText(PASSWORD)

    dialog.attempt_login()

    assert dialog.result_session is not None
    assert dialog.result_session.user_email == "ui_admin@arca.test"
    assert dialog.result() == QDialog.Accepted
    assert dialog.error_label.text() == ""


def test_login_fallido_error_en_linea_sin_popup(qtbot, db):
    store = auth.SessionStore()
    add_user(db, "ui_bad@arca.test", "observador")

    dialog = LoginDialog(lambda email, password: auth.login(db, store, email, password))
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.email_edit.setText("ui_bad@arca.test")
    dialog.password_edit.setText("clave-mala")

    dialog.attempt_login()

    assert dialog.result_session is None
    assert dialog.result() != QDialog.Accepted
    assert "Usuario o contraseña incorrectos" in dialog.error_label.text()
    assert dialog.isVisible()  # stays open, no popups


# ---------------------------------------------------------------- MainWindow


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", ["dashboard", "synoptic", "summary", "audit", "maintenance", "admin"]),
        ("administrador", ["dashboard", "synoptic", "summary", "audit", "maintenance", "admin"]),
        ("control_calidad", ["dashboard", "synoptic", "summary", "audit", "maintenance"]),
        ("encargado", ["dashboard", "synoptic", "summary", "maintenance"]),
        ("observador", ["dashboard", "synoptic", "summary", "maintenance"]),
    ],
)
def test_nav_filtrada_por_rol(qtbot, db, role, expected):
    window = MainWindow(role=role, db_path=db)
    qtbot.addWidget(window)
    assert window.visible_pages() == expected


def test_nav_observador_no_ve_auditoria_ni_seguridad(qtbot, db):
    window = MainWindow(role="observador", db_path=db)
    qtbot.addWidget(window)
    assert "audit" not in window.visible_pages()
    assert "admin" not in window.visible_pages()


# ---------------------------------------------------------------- StationsAdminPage


def test_station_create_roundtrip_desde_la_ui(qtbot, db):
    page = StationsAdminPage(db)
    qtbot.addWidget(page)
    page.refresh()
    assert page.row_count() == 15  # seed stations

    page.set_form("TEST01", "Estación UI", "Santo Domingo", 18.5, -69.9, 10.0, 1.5)
    page.create_clicked()

    row = stations_repo.get_station(db, "TEST01")
    assert row is not None and row.name == "Estación UI"
    assert page.row_count() == 16
    assert page.find_row("TEST01") is not None


def test_station_deactivate_desde_la_ui(qtbot, db):
    page = StationsAdminPage(db)
    qtbot.addWidget(page)
    page.refresh()
    page.select_station("78451")
    page.deactivate_clicked()

    row = stations_repo.get_station(db, "78451")
    assert row.is_active is False
    # still listed when inactive are included; hidden by default filter
    assert page.find_row("78451") is None
    page.set_include_inactive(True)
    assert page.find_row("78451") is not None
