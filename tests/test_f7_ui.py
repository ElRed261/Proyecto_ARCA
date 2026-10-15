"""F7 — pytest-qt UI + thread tests (QT_QPA_PLATFORM=offscreen, see conftest).

Probe honesty, maintenance page (paths / sync panel / threaded retry /
admin-gated migration), dashboard scoping per role, SyncWorker stop flag +
signals, antifreeze (event loop ticks while a slow sync runs — no wall
sleeps), and MainWindow showing only real pages.
"""

from __future__ import annotations

import threading

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QTabWidget

from oms_core import paths as paths_mod
from oms_core.db.repositories import observations as observations_repo
from oms_core.db.repositories import stations as stations_repo
from oms_core.services import sync as sync_service
from oms_core.services.sync_thread import SyncWorker
from oms_ui.main_window import MainWindow
from oms_ui.pages.dashboard import DashboardPage
from oms_ui.pages.maintenance import MaintenancePage, PathCard, probe_path

STATION = "78485"
TODAY = "2025-12-08"


def _seed_observation(conn, station=STATION, fecha=TODAY, hora="06Z"):
    observations_repo.upsert_observation(
        conn,
        observations_repo.Observation(
            station_id=station,
            fecha=fecha,
            hora=hora,
            p_est=1015.0,
            p_nmm=1016.0,
            rocio=20.0,
            t_vapor=23.0,
            hr=90.0,
            v_dir_deg=90.0,
            v_vel=3.0,
            observador="Test",
            source_sha256="seed",
        ),
    )


def _seed_pending(conn, offline, relative="synop/78485/2025/12/f.json", payload=b"datum"):
    source = offline / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    sync_service.enqueue(conn, sync_service.SyncRow("synop", "78485", relative, str(source)))
    return source


# ------------------------------------------------------------------- probe


def test_probe_ok_on_writable_dir(tmp_path):
    result = probe_path(str(tmp_path / "new-root"))
    assert result.writable is True
    assert (tmp_path / "new-root").is_dir()
    assert list((tmp_path / "new-root").glob(".arca_probe_*")) == []


def test_probe_fails_honestly_on_file_and_empty(tmp_path):
    victim = tmp_path / "file.txt"
    victim.write_text("x")
    bad = probe_path(str(victim))
    assert bad.writable is False and bad.error
    empty = probe_path("")
    assert empty.writable is False and empty.error


def test_path_card_probe_button_shows_honest_state(qtbot, tmp_path):
    card = PathCard("Root", "hint")
    qtbot.addWidget(card)

    card.edit.setText(str(tmp_path))
    qtbot.mouseClick(card.probe_button, Qt.LeftButton)
    assert "✓" in card.result_label.text()

    victim = tmp_path / "file.txt"
    victim.write_text("x")
    card.edit.setText(str(victim))
    qtbot.mouseClick(card.probe_button, Qt.LeftButton)
    assert "✗" in card.result_label.text()


# ---------------------------------------------------------- maintenance page


def test_maintenance_loads_profile_and_saves(qtbot, fresh_db, tmp_path):
    paths_mod.set_path_profile(
        fresh_db,
        paths_mod.PathProfile(
            offline_root=str(tmp_path / "off"),
            online_root=str(tmp_path / "on"),
            summaries_dir=str(tmp_path / "sum"),
            backups_max_age_days=30,
        ),
    )
    page = MaintenancePage(fresh_db, role="admin")
    qtbot.addWidget(page)

    assert page.cards["offline_root"].edit.text() == str(tmp_path / "off")
    assert page.backups_spin.value() == 30

    page.cards["online_root"].edit.setText(str(tmp_path / "on2"))
    assert page.save_profile() is True
    saved = paths_mod.get_path_profile(fresh_db)
    assert saved is not None and saved.online_root == str(tmp_path / "on2")
    assert "guardada" in page.save_label.text()


def test_maintenance_edit_and_migration_are_admin_gated(qtbot, fresh_db):
    page = MaintenancePage(fresh_db, role="observador")
    qtbot.addWidget(page)

    assert page.can_edit is False
    assert page.save_button is None
    assert page.migrate_button is None
    assert all(not card.edit.isEnabled() for card in page.cards.values())
    # ... but the sync panel stays visible to every role
    assert "Pendientes" in page.pending_label.text()


def test_maintenance_sync_panel_shows_pending_and_error(qtbot, fresh_db, tmp_path):
    offline = tmp_path / "off"
    offline.mkdir()
    emit = sync_service.emit_after_save(
        fresh_db,
        offline,
        tmp_path / "on",
        "synop",
        "78485",
        "2025",
        "12",
        "f.json",
        transport=_broken_transport,
    )
    assert emit.error is not None

    page = MaintenancePage(fresh_db, role="admin")
    qtbot.addWidget(page)

    assert "1" in page.pending_label.text()
    assert "drive asleep" in page.last_error_label.text()
    assert page.error_list.count() == 1


def _broken_transport(source, target):
    raise OSError("drive asleep")


def test_maintenance_retry_now_goes_through_the_thread(qtbot, fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    paths_mod.set_path_profile(
        fresh_db,
        paths_mod.PathProfile(offline_root=str(offline), online_root=str(online)),
    )
    _seed_pending(fresh_db, offline)

    page = MaintenancePage(fresh_db, role="admin", transport=sync_service.copy_transport)
    qtbot.addWidget(page)

    qtbot.mouseClick(page.retry_button, Qt.LeftButton)
    worker = page._worker
    assert isinstance(worker, SyncWorker)
    # waitUntil pumps the event loop: race-free even if the worker finished
    # before we got here (this pytest-qt needs .wait()/context form to block).
    qtbot.waitUntil(lambda: "Sincronizados: 1" in page.sync_status_label.text(), timeout=15000)

    assert page.progress_bar.value() == 100  # progress signal arrived
    assert "Pendientes de enviar: 0" in page.pending_label.text()
    assert page.retry_button.isEnabled()


def test_maintenance_migration_runs_on_configured_base(qtbot, fresh_db, tmp_path):
    base = tmp_path / "base"
    legacy = base / "synop" / "78485" / "2025" / "mayo"
    legacy.mkdir(parents=True)
    (legacy / "f.json").write_text("{}")
    paths_mod.set_path_profile(fresh_db, paths_mod.PathProfile(offline_root=str(base)))

    page = MaintenancePage(fresh_db, role="admin")
    qtbot.addWidget(page)
    qtbot.mouseClick(page.migrate_button, Qt.LeftButton)

    assert "1 carpetas" in page.migrate_label.text()
    assert (base / "synop" / "78485" / "2025" / "05" / "f.json").exists()


# ------------------------------------------------------------------ worker


def _seed_rows(conn, offline, count, payload=b"x" * 4096):
    for i in range(count):
        relative = f"synop/78485/2025/12/f{i}.json"
        _seed_pending(conn, offline, relative, payload)


def test_worker_stop_flag_cancels_a_slow_sync(qtbot, fresh_db, tmp_path):
    offline = tmp_path / "off"
    online = tmp_path / "on"
    _seed_rows(fresh_db, offline, 5)
    db_file = fresh_db.execute("PRAGMA database_list").fetchall()[0][2]

    release = threading.Event()
    calls: list[int] = []

    def gated(source, target):
        calls.append(1)
        if len(calls) > 1:
            assert release.wait(timeout=10)
        return sync_service.copy_transport(source, target)

    worker = SyncWorker(db_file, offline, online, force=True, transport=gated)
    outcomes: list[dict] = []
    progresses: list[tuple[int, int]] = []
    worker.progress.connect(lambda d, t: progresses.append((d, t)))
    worker.outcome.connect(outcomes.append)
    progress_blocker = qtbot.waitSignal(worker.progress, timeout=10000)
    outcome_blocker = qtbot.waitSignal(worker.outcome, timeout=15000)
    worker.start()
    progress_blocker.wait()

    worker.request_stop()
    release.set()
    outcome_blocker.wait()
    worker.wait(5000)

    assert outcomes and outcomes[0]["stopped"] is True
    assert outcomes[0]["attempted"] < 5
    assert progresses  # the GUI thread heard back at least once


def test_worker_reports_broken_database_without_raising(qtbot, tmp_path):
    outcomes: list[dict] = []
    worker = SyncWorker(tmp_path / "no-such-dir" / "q.db", tmp_path, tmp_path)
    worker.outcome.connect(outcomes.append)
    blocker = qtbot.waitSignal(worker.outcome, timeout=15000)
    worker.start()
    blocker.wait()
    worker.wait(5000)
    assert outcomes and outcomes[0]["error"]


def test_sync_never_freezes_the_event_loop(qtbot, fresh_db, tmp_path):
    """Antifreeze: timer ticks keep firing while the worker syncs."""
    offline = tmp_path / "off"
    online = tmp_path / "on"
    # A genuinely slow sync: 25 real 512 KiB copies + hashes (~13 MB of I/O).
    _seed_rows(fresh_db, offline, 25, payload=b"y" * 524288)
    db_file = fresh_db.execute("PRAGMA database_list").fetchall()[0][2]

    ticks: list[int] = []
    timer = QTimer()
    timer.setInterval(0)  # fire whenever the loop is idle during the op
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()

    outcomes: list[dict] = []
    worker = SyncWorker(db_file, offline, online, force=True)
    worker.outcome.connect(outcomes.append)
    blocker = qtbot.waitSignal(worker.outcome, timeout=15000)
    worker.start()
    blocker.wait()
    worker.wait(5000)
    timer.stop()

    assert outcomes and outcomes[0]["marked_synced"] == 25
    assert len(ticks) > 0, "event loop starved while syncing"


# ---------------------------------------------------------------- dashboard


def test_admin_sees_all_station_cards(qtbot, fresh_db):
    _seed_observation(fresh_db, "78485", TODAY, "06Z")
    _seed_observation(fresh_db, "78485", TODAY, "12Z")
    _seed_observation(fresh_db, "78486", TODAY, "06Z")

    page = DashboardPage(fresh_db, role="admin", today=TODAY)
    qtbot.addWidget(page)

    assert page.scope == "all"
    assert set(page.station_cards) == {s.id for s in stations_repo.list_stations(fresh_db)}
    assert "2/8" in page.station_cards["78485"].today_label.text()
    assert "1/8" in page.station_cards["78486"].today_label.text()
    assert "días con datos" in page.station_cards["78485"].month_label.text()


def test_observador_locked_to_assigned_station(qtbot, fresh_db):
    _seed_observation(fresh_db)

    page = DashboardPage(fresh_db, role="observador", assigned_station="78485", today=TODAY)
    qtbot.addWidget(page)

    assert page.scope == "78485"
    assert list(page.station_cards) == ["78485"]
    assert "78485" in page.lock_label.text()
    assert "Tu estación" in page.lock_label.text()


def test_privileged_lock_banner_mentions_instance(qtbot, fresh_db):
    page = DashboardPage(fresh_db, role="control_calidad", assigned_station="78485", today=TODAY)
    qtbot.addWidget(page)

    assert set(page.station_cards) == {s.id for s in stations_repo.list_stations(fresh_db)}
    assert "bloqueada" in page.lock_label.text()


def test_non_privileged_without_station_shows_honest_banner(qtbot, fresh_db):
    page = DashboardPage(fresh_db, role="observador", today=TODAY)
    qtbot.addWidget(page)

    assert page.scope is None
    assert page.station_cards == {}
    assert "Sin estación asignada" in page.lock_label.text()


def test_sync_badge_reflects_pending_count(qtbot, fresh_db, tmp_path):
    _seed_pending(fresh_db, tmp_path / "off")

    page = DashboardPage(fresh_db, role="admin", today=TODAY)
    qtbot.addWidget(page)
    assert "1 pendiente" in page.sync_label.text()


def test_dashboard_navigate_buttons_call_back(qtbot, fresh_db):
    _seed_observation(fresh_db)
    seen: list[str] = []
    page = DashboardPage(
        fresh_db,
        role="observador",
        assigned_station="78485",
        on_navigate=seen.append,
        today=TODAY,
    )
    qtbot.addWidget(page)

    qtbot.mouseClick(page.station_cards["78485"].go_button, Qt.LeftButton)
    qtbot.mouseClick(page.sync_button, Qt.LeftButton)
    assert seen == ["synoptic", "maintenance"]


# ---------------------------------------------------------------- main window


def _assert_no_placeholders(window: MainWindow) -> None:
    leftovers = [
        label.text() for label in window.findChildren(QLabel) if "pendiente" in label.text()
    ]
    assert leftovers == []


def test_main_window_shows_real_pages_for_admin(qtbot, fresh_db):
    from oms_ui.pages.audit import AuditPage
    from oms_ui.pages.audit_report import AuditReportPage
    from oms_ui.pages.stations_admin import StationsAdminPage
    from oms_ui.pages.summary import SummaryPage
    from oms_ui.pages.synoptic import SynopticPage

    window = MainWindow(role="admin", db_path=fresh_db)
    qtbot.addWidget(window)

    assert window.visible_pages() == [
        "dashboard",
        "synoptic",
        "summary",
        "audit",
        "maintenance",
        "admin",
    ]
    assert isinstance(window._pages["dashboard"], DashboardPage)
    assert isinstance(window._pages["synoptic"], SynopticPage)
    assert isinstance(window._pages["summary"], SummaryPage)
    assert isinstance(window._pages["admin"], StationsAdminPage)
    assert isinstance(window._pages["maintenance"], MaintenancePage)
    audit_tabs = window._pages["audit"]
    assert isinstance(audit_tabs, QTabWidget)
    assert isinstance(audit_tabs.widget(0), AuditPage)
    assert isinstance(audit_tabs.widget(1), AuditReportPage)
    _assert_no_placeholders(window)


def test_main_window_shows_real_pages_for_observador(qtbot, fresh_db):
    window = MainWindow(role="observador", db_path=fresh_db)
    qtbot.addWidget(window)

    assert window.visible_pages() == ["dashboard", "synoptic", "summary", "maintenance"]
    assert isinstance(window._pages["dashboard"], DashboardPage)
    assert isinstance(window._pages["maintenance"], MaintenancePage)
    _assert_no_placeholders(window)


def test_main_window_dashboard_shortcut_navigates(qtbot, fresh_db):
    window = MainWindow(role="admin", db_path=fresh_db)
    qtbot.addWidget(window)
    window.show()

    dashboard: DashboardPage = window._pages["dashboard"]
    qtbot.mouseClick(dashboard.sync_button, Qt.LeftButton)
    assert window.stack.currentWidget() is window._pages["maintenance"]


def test_dashboard_grid_responsive_columns(qtbot, fresh_db):
    """Narrow (1 col) vs comfortable (2 cols) card layout (IMG Panel)."""
    from oms_ui.pages.dashboard import DashboardPage

    page = DashboardPage(fresh_db, role="admin", today="2025-12-08")
    qtbot.addWidget(page)
    page.show()
    codes = page._card_codes
    assert len(codes) >= 2

    page.resize(500, 700)
    qtbot.wait(100)
    row, col, _, _ = page._grid.getItemPosition(1)
    assert (row, col) == (1, 0)

    page.resize(800, 700)
    qtbot.wait(100)
    row, col, _, _ = page._grid.getItemPosition(1)
    assert (row, col) == (0, 1)


def test_operations_center_grid_fills_page_height(qtbot, fresh_db):
    """Owner round 3: the grid+sync card column owns the FULL page height;
    the trailing stretch used to split the center at half the screen."""
    from PySide6.QtWidgets import QApplication, QScrollArea

    page = DashboardPage(fresh_db, role="admin",
                         on_navigate=lambda _pid: None, parent=None)
    qtbot.addWidget(page)
    page.resize(1200, 640)
    page.show()
    for _ in range(6):
        QApplication.processEvents()
    areas = page.findChildren(QScrollArea)
    assert areas, "dashboard must keep its card scroll area"
    viewport = areas[0].viewport().height()
    assert viewport >= page.height() * 0.55, (
        f"center grid collapsed: viewport {viewport} / page {page.height()}"
    )
    assert page.station_cards  # the responsive grid still owns its cards
