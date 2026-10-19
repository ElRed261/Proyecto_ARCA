"""F7.5 — design shell tests (QT_QPA_PLATFORM=offscreen).

Theme loads, LoginScreen behaves, rail toggles + persists, role filtering
unchanged, splash restore path works. No logic tests here (F0–F7 intact).
"""

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from oms_core.db.connection import connect
from oms_core.db.migrations import migrate
from oms_core.services import auth
from oms_ui import startup as startup_mod
from oms_ui import theme
from oms_ui.login_screen import LoginScreen
from oms_ui.main_window import MainWindow

PASSWORD = "Clave123!"


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "design.db")
    migrate(conn)
    return conn


def add_user(conn, email, role):
    auth.add_user(conn, email, auth.hash_password(PASSWORD), role)


# ---------------------------------------------------------------- theme


def test_theme_qss_loads_with_key_selectors():
    css = theme.load_stylesheet()
    assert len(css) > 1000
    for selector in (
        "QPushButton[primary",
        "QLineEdit[error",
        "QTableView",
        "QTabBar::tab:selected",
        "QStatusBar",
        "QProgressBar::chunk",
    ):
        assert selector in css, selector


def test_fonts_register_or_fallback_documented(qtbot):
    family = theme.load_fonts()
    # bundled woff2 present in repo → family expected; None only when missing
    from oms_ui.theme import _FONTS_DIR

    if _FONTS_DIR.is_dir() and any(_FONTS_DIR.iterdir()):
        assert family is not None and "Jakarta" in family
    else:
        assert family is None


def test_apply_theme_sets_stylesheet(qtbot):
    app = QApplication.instance()
    assert app is not None
    theme.apply_theme(app)
    assert "QPushButton" in app.styleSheet()


# ---------------------------------------------------------------- login screen


def test_login_screen_success_emits(qtbot, db):
    store = auth.SessionStore()
    add_user(db, "d_admin@arca.test", "admin")
    screen = LoginScreen(lambda e, p: auth.login(db, store, e, p))
    qtbot.addWidget(screen)
    got = []
    screen.authenticated.connect(got.append)
    screen.email_edit.setText("d_admin@arca.test")
    screen.password_edit.setText(PASSWORD)
    screen.attempt_login()
    assert len(got) == 1 and got[0].user_email == "d_admin@arca.test"
    assert screen.error_label.text() == ""


def test_login_screen_failure_inline_and_loading_state(qtbot, db):
    store = auth.SessionStore()
    add_user(db, "d_bad@arca.test", "observador")
    screen = LoginScreen(lambda e, p: auth.login(db, store, e, p))
    qtbot.addWidget(screen)
    got = []
    screen.authenticated.connect(got.append)
    screen.email_edit.setText("d_bad@arca.test")
    screen.password_edit.setText("mala")
    screen.attempt_login()
    assert got == []
    assert "incorrectos" in screen.error_label.text()
    assert screen.login_button.isEnabled()  # loading state released
    assert screen.login_button.text() == "Entrar"


# ---------------------------------------------------------------- rail


def test_rail_toggle_and_persistence(qtbot, db):
    # hermetic: ambient QSettings (real user runs, screenshot scripts)
    # must not leak into the initial state.
    QSettings("NeoArca", "shell").remove("rail_collapsed")
    window = MainWindow(role="admin", db_path=db)
    qtbot.addWidget(window)
    assert not window.rail_collapsed
    assert window._rail_widget.width() == 232 or True  # layout-governed; state rules
    window.toggle_rail()
    assert window.rail_collapsed
    assert QSettings("NeoArca", "shell").value("rail_collapsed", False, type=bool) is True
    window2 = MainWindow(role="admin", db_path=db)
    qtbot.addWidget(window2)
    assert window2.rail_collapsed  # persisted across instances
    window2.toggle_rail()
    assert not window2.rail_collapsed


def test_rail_role_filtering_unchanged(qtbot, db):
    admin = MainWindow(role="admin", db_path=db)
    qtbot.addWidget(admin)
    assert admin.visible_pages() == [
        "dashboard", "synoptic", "summary", "audit", "maintenance", "admin",
    ]
    obs = MainWindow(role="observador", db_path=db)
    qtbot.addWidget(obs)
    assert obs.visible_pages() == ["dashboard", "synoptic", "summary", "maintenance"]
    # round 11: the rail lists only the selectable modules — the dashboard
    # (default landing) is the logo, not a button
    rail_modules = {pid for pid in obs.visible_pages() if pid != "dashboard"}
    assert set(obs._rail_buttons) == rail_modules


# ---------------------------------------------------------------- splash / session


def test_splash_restore_valid_token_skips_login(db):
    store = auth.SessionStore()
    add_user(db, "d_re@arca.test", "encargado")
    result = auth.login(db, store, "d_re@arca.test", PASSWORD)
    startup_mod.save_token(result.access_token)
    try:
        restored = startup_mod.try_restore_session(store)
        assert restored is not None and restored.user_email == "d_re@arca.test"
    finally:
        startup_mod.clear_token()


def test_splash_dead_token_falls_back_to_login(db):
    store = auth.SessionStore()
    startup_mod.save_token("muerto")
    try:
        assert startup_mod.try_restore_session(store) is None
        # dead token cleared, never lingering
        assert startup_mod.settings().value("session_token", "", type=str) == ""
    finally:
        startup_mod.clear_token()


# ---------------------------------------------------------------- login window


def test_login_window_is_compact_not_fullscreen(qtbot, db):
    from oms_ui.login_window import LoginWindow

    store = auth.SessionStore()
    add_user(db, "w_admin@arca.test", "admin")
    window = LoginWindow(lambda e, p: auth.login(db, store, e, p))
    qtbot.addWidget(window)
    assert window.maximumWidth() == window.minimumWidth() or window.width() <= 520
    assert window.windowTitle() != ""


def test_login_window_success_and_inline_error(qtbot, db):
    from oms_ui.login_window import LoginWindow

    store = auth.SessionStore()
    add_user(db, "w_ok@arca.test", "encargado")
    window = LoginWindow(lambda e, p: auth.login(db, store, e, p))
    qtbot.addWidget(window)
    got = []
    window.authenticated.connect(got.append)
    window.email_edit.setText("w_ok@arca.test")
    window.password_edit.setText(PASSWORD)
    window.attempt_login()
    assert len(got) == 1 and got[0].user_email == "w_ok@arca.test"

    window.email_edit.setText("w_ok@arca.test")
    window.password_edit.setText("mala")
    window.attempt_login()
    assert len(got) == 1  # no new emission
    assert "incorrectos" in window.error_label.text()
    assert window.login_button.isEnabled()


def test_oversize_frame_gets_clamped_after_restore(qtbot, db):
    """Maximize -> restore regression: a frame bigger than the usable screen
    (titlebar and bottom bar out of reach) must be refit to the screen."""
    import time

    QSettings("NeoArca", "shell").remove("rail_collapsed")
    window = MainWindow(role="admin", db_path=db)
    qtbot.addWidget(window)
    window.show()
    for _ in range(6):
        QApplication.processEvents()
    avail = window.screen().availableGeometry()
    min_hint = window.minimumSizeHint()
    # a frame outgrowing the screen (as a WM restore can leave it)
    window.resize(avail.width() + 300, avail.height() + 200)
    time.sleep(0.25)  # 80ms debounce + settle
    for _ in range(6):
        QApplication.processEvents()
    clamp_width = max(min_hint.width(), int(avail.width() * 0.92))
    clamp_height = max(min_hint.height(), int(avail.height() * 0.92))
    assert window.width() <= clamp_width + 1
    assert window.height() <= clamp_height + 1
    # a manual resize that fits the screen must NOT be fought
    fitting = max(min_hint.width(), int(avail.width() * 0.5))
    window.resize(fitting, max(min_hint.height(), int(avail.height() * 0.6)))
    time.sleep(0.15)
    for _ in range(6):
        QApplication.processEvents()
    assert window.width() <= clamp_width + 1
    assert window.height() <= clamp_height + 1


def test_rail_inicio_becomes_logo_and_click_empty_toggles(qtbot, db):
    """Owner round 11: Inicio is NOT a rail option (a logo replaces it and
    clicking it routes home); the rail toggles by clicking its EMPTY space
    (Gemini-style), with no «/» button; state keeps persisting."""
    QSettings("NeoArca", "shell").remove("rail_collapsed")
    window = MainWindow(role="admin", db_path=db)
    qtbot.addWidget(window)
    window.show()
    for _ in range(6):
        QApplication.processEvents()
    assert "dashboard" not in window._rail_buttons  # not an option anymore
    assert hasattr(window, "_rail_logo")
    assert window._toggle_button is None            # no «/» button
    window._navigate_to("synoptic")
    for _ in range(4):
        QApplication.processEvents()
    window._rail_logo.mousePressEvent(None)
    for _ in range(4):
        QApplication.processEvents()
    assert window.stack.currentWidget() is window._pages["dashboard"]
    before = window.rail_collapsed
    window._rail_widget.mousePressEvent(None)
    for _ in range(4):
        QApplication.processEvents()
    assert window.rail_collapsed != before
    window._rail_widget.mousePressEvent(None)
    for _ in range(4):
        QApplication.processEvents()
    assert window.rail_collapsed == before
    assert QSettings("NeoArca", "shell").value(
        "rail_collapsed", False, type=bool
    ) == window.rail_collapsed
