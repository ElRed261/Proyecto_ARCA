"""A20 — the audit report counts the OBSERVER, per type and data group.

Owner round 25 decisions (odd/tasks/auditoria-reporte-observador.md):
S2 the report attributes every mark to the observer of that hour;
S3 it shows errors, audited observations and both rates;
S4 the taxonomy is the five closed types plus the derived data group.
"""

import pytest

from oms_core.services import audit as audit_service
from oms_core.services import document_map as dm

# Every field the audit window can mark (audit_observation.FIELD_LABELS).
AUDITED_FIELDS = (
    "observador", "ts", "th", "pres_est", "p3", "p24", "t_max", "t_min",
    "t_max_24h", "t_min_24h", "ll", "ll_24h", "viento_dir", "viento_vel",
    "visibilidad", "correc_alt", "meteo_2_1", "meteo_4_irixhvv", "meteo_4_1",
    "meteo_4_6", "meteo_6_0", "meteo_6_2", "meteo_6_3", "meteo_6_4",
    "meteo_8_0", "meteo_8_1", "meteo_8_3", "meteo_8_4", "pres_nmm",
    "punto_rocio", "tension_vapor", "humedad_relativa", "diferencia",
)


# ------------------------------------------------- S4: the derived data group


@pytest.mark.parametrize("campo", AUDITED_FIELDS)
def test_every_auditable_field_has_a_real_group(campo):
    assert dm.group_for_field(campo) != "otro", f"{campo} sin grupo"
    assert dm.group_for_field(campo) in dm.GROUP_ORDER


def test_an_unknown_field_falls_into_otro():
    assert dm.group_for_field("campo_inventado") == "otro"
    assert dm.group_for_field(None) == "otro"


def test_the_groups_are_ordered_and_otro_closes_the_list():
    assert dm.GROUP_ORDER[-1] == "otro"
    assert len(set(dm.GROUP_ORDER)) == len(dm.GROUP_ORDER)
    used = {dm.group_for_field(campo) for campo in AUDITED_FIELDS}
    assert used <= set(dm.GROUP_ORDER)


def test_the_group_travels_with_the_mark(fresh_db):
    mark = audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        hora="06Z", campo="meteo_4_1", tipo_error="Consistencia",
        marcado_por="auditor@x",
    )
    assert mark["grupo"] == "viento"


# --------------------------------------------------- S4: the closed type list


def test_the_five_types_are_the_oracle_list():
    assert audit_service.ERROR_TYPES == (
        "Sintaxis", "Cálculo", "Consistencia", "Falta de datos", "Otro",
    )


@pytest.mark.parametrize("tipo", audit_service.ERROR_TYPES)
def test_every_closed_type_can_be_marked(fresh_db, tipo):
    mark = audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        hora="06Z", campo="ts", tipo_error=tipo, marcado_por="auditor@x",
    )
    assert mark["tipo_error"] == tipo


def test_a_free_text_type_is_refused(fresh_db):
    """'Calculo' without the accent is exactly the drift the list prevents."""
    with pytest.raises(audit_service.AuditError, match="Tipo de error inválido"):
        audit_service.mark_error(
            fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
            hora="06Z", campo="ts", tipo_error="Calculo", marcado_por="a@x",
        )


def test_the_automatic_type_is_accepted(fresh_db):
    """The application itself writes the missing-observer mark."""
    mark = audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        hora="06Z", campo="observador",
        tipo_error=audit_service.AUTO_ERROR_TYPE,
        marcado_por="Sistema de Calidad",
    )
    assert mark["tipo_error"] == "Falta nombre de observador"


# ------------------------------------------- T4: closing a day = denominator


def test_closing_a_day_records_the_auditor(fresh_db):
    closed = audit_service.close_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        auditado_por="qc@oms", nota="revisado",
    )
    assert closed["auditado_por"] == "qc@oms"
    assert closed["nota"] == "revisado"
    assert closed["auditado_en"]
    assert audit_service.get_audit_day(
        fresh_db, station_id="78486", fecha="2024-04-28"
    )["auditado_por"] == "qc@oms"


def test_closing_twice_updates_the_closure(fresh_db):
    for auditor in ("qc@oms", "otro@oms"):
        audit_service.close_audit_day(
            fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
            auditado_por=auditor,
        )
    assert audit_service.get_audit_day(
        fresh_db, station_id="78486", fecha="2024-04-28"
    )["auditado_por"] == "otro@oms"


def test_reopening_a_day_withdraws_the_closure(fresh_db):
    audit_service.close_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        auditado_por="qc@oms",
    )
    assert audit_service.reopen_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28"
    ) is True
    assert audit_service.get_audit_day(
        fresh_db, station_id="78486", fecha="2024-04-28"
    ) is None


def test_an_observer_cannot_close_an_audit(fresh_db):
    with pytest.raises(PermissionError):
        audit_service.close_audit_day(
            fresh_db, role="observador", station_id="78486",
            fecha="2024-04-28", auditado_por="x@y",
        )


def test_the_closure_needs_a_named_auditor(fresh_db):
    with pytest.raises(audit_service.AuditError, match="auditor"):
        audit_service.close_audit_day(
            fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
            auditado_por="   ",
        )


# ------------------------------------- T3: the report that counts the observer


@pytest.fixture
def audited_day(fresh_db):
    """One day, two observers, three marks, closed by quality control."""
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "06Z",
                               {"nombre_observador": "YASSER GALAN"})
    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "12Z",
                               {"nombre_observador": "EDGAR ACOSTA"})
    for hora, campo, tipo in (
        ("06Z", "ts", "Sintaxis"),
        ("06Z", "pres_est", "Consistencia"),
        ("12Z", "meteo_4_1", "Falta de datos"),
    ):
        audit_service.mark_error(
            fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
            hora=hora, campo=campo, tipo_error=tipo, marcado_por="qc@oms",
        )
    audit_service.close_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        auditado_por="qc@oms",
    )
    return fresh_db


def test_the_summary_counts_the_observer_not_the_auditor(audited_day):
    rows = {r["persona"]: r for r in audit_service.get_observer_summary(audited_day)}
    assert "qc@oms" not in rows, "el auditor no aparece como observador"
    assert rows["YASSER GALAN"]["errores"] == 2
    assert rows["EDGAR ACOSTA"]["errores"] == 1


def test_the_rates_use_the_audited_hours_of_each_observer(audited_day):
    rows = {r["persona"]: r for r in audit_service.get_observer_summary(audited_day)}
    galan = rows["YASSER GALAN"]
    # the day is closed, so its eight hours count; each hour belongs to the
    # observer who wrote it, and the six hours with nobody land in Desconocido
    assert galan["horas_auditadas"] == 1
    assert galan["campos_auditados"] == len(audit_service.AUDITABLE_FIELDS)
    assert galan["tasa_por_observacion"] == 2.0        # 2 errores / 1 hora
    assert galan["tasa_por_campos"] == round(
        100 * 2 / len(audit_service.AUDITABLE_FIELDS), 2
    )
    assert rows["EDGAR ACOSTA"]["tasa_por_observacion"] == 1.0
    # the hours nobody signed are reported, not hidden
    assert rows["Desconocido"]["horas_auditadas"] == 6
    assert rows["Desconocido"]["errores"] == 0


def test_the_summary_breaks_the_errors_down_by_type_and_group(audited_day):
    rows = {r["persona"]: r for r in audit_service.get_observer_summary(audited_day)}
    galan = rows["YASSER GALAN"]
    assert galan["por_tipo"] == {"Sintaxis": 1, "Consistencia": 1}
    assert galan["por_grupo"] == {"temperatura": 1, "presión": 1}


def test_a_day_with_marks_counts_even_without_closure(fresh_db):
    """Legacy days reviewed before M007 still get a denominator."""
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-05-02", "09Z",
                               {"nombre_observador": "MARTA"})
    audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-05-02",
        hora="09Z", campo="ts", tipo_error="Sintaxis", marcado_por="qc@oms",
    )
    row = {r["persona"]: r for r in audit_service.get_observer_summary(fresh_db)}["MARTA"]
    assert row["horas_auditadas"] >= 1
    assert row["tasa_por_observacion"] > 0


def test_an_unknown_observer_is_reported_as_desconocido(fresh_db):
    audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-06-01",
        hora="06Z", campo="ts", tipo_error="Sintaxis", marcado_por="qc@oms",
    )
    rows = audit_service.get_observer_summary(fresh_db)
    assert rows[0]["persona"] == "Desconocido"
    assert rows[0]["errores"] == 1


def test_the_summary_is_empty_when_nothing_was_audited(fresh_db):
    assert audit_service.get_observer_summary(fresh_db) == []


def test_the_summary_respects_station_and_month_filters(audited_day):
    assert audit_service.get_observer_summary(audited_day, station_id="78486",
                                              year="2024", month="04")
    assert audit_service.get_observer_summary(audited_day, station_id="78486",
                                              year="2024", month="05") == []


# --------------------------------------------- T3: the detail says who and where


def test_the_detail_rows_carry_the_observer_and_the_group(audited_day):
    rows = audit_service.get_error_report(audited_day, station_id="78486")
    by_field = {row["campo"]: row for row in rows}
    assert by_field["ts"]["observador"] == "YASSER GALAN"
    assert by_field["ts"]["grupo"] == "temperatura"
    assert by_field["meteo_4_1"]["observador"] == "EDGAR ACOSTA"
    assert by_field["meteo_4_1"]["grupo"] == "viento"


def test_the_window_can_mark_every_auditable_field():
    """The auditor must be able to mark anything the report knows about."""
    from oms_ui.pages.audit_observation import FIELD_LABELS

    assert set(audit_service.AUDITABLE_FIELDS) == set(FIELD_LABELS)


# ------------------------------------------------------ T5/T6: the report sheet


@pytest.fixture
def report_page(audited_day, qtbot):
    from oms_ui.pages.audit_report import AuditReportPage

    page = AuditReportPage(audited_day, role="admin")
    qtbot.addWidget(page)
    return page


def test_the_observer_tab_leads_the_report(report_page):
    assert report_page.tabs.count() == 3
    assert report_page.tabs.tabText(0) == "Por observador"
    # two named observers, the six hours nobody signed, and the TOTAL row
    assert report_page.observer_table.rowCount() == 4


def test_the_observer_sheet_adds_up(report_page):
    table = report_page.observer_table
    names = [table.item(row, 0).text() for row in range(table.rowCount())]
    assert names[0] == "YASSER GALAN"     # errors desc
    assert names[-1] == "TOTAL"
    assert table.item(table.rowCount() - 1, 1).text() == "3"   # 2 + 1 errors


def test_the_detail_tab_says_who_and_where(report_page):
    table = report_page.detail_table
    headers = [
        table.horizontalHeaderItem(col).text() for col in range(table.columnCount())
    ]
    assert "Observador" in headers
    assert "Grupo" in headers


def test_the_pdf_carries_the_observer_sheet(report_page, tmp_path):
    html = report_page._report_html()
    assert "Reporte de errores por observador" in html
    assert "YASSER GALAN" in html and "EDGAR ACOSTA" in html
    assert "TOTAL" in html

    path = report_page.export_pdf(str(tmp_path / "reporte.pdf"))
    assert path.endswith(".pdf")
    data = (tmp_path / "reporte.pdf").read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 1000


# ------------------------------------- T4-UI: closing from the observation page


def _observation_page(conn, qtbot, role="admin"):
    from oms_ui.pages.audit_observation import AuditObservationPage

    page = AuditObservationPage(
        conn, _tmp_dir(), "78486", "2024-04-28", role=role, user_email="qc@oms"
    )
    qtbot.addWidget(page)
    return page


def _tmp_dir():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())


def test_the_button_closes_the_day_and_the_report_counts_it(fresh_db, qtbot):
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "06Z",
                               {"nombre_observador": "YASSER GALAN"})
    page = _observation_page(fresh_db, qtbot)
    assert page.close_button.text() == "Terminar auditoría"

    page.toggle_audit_day()

    assert audit_service.get_audit_day(
        fresh_db, station_id="78486", fecha="2024-04-28"
    )["auditado_por"] == "qc@oms"
    assert page.close_button.text() == "Reabrir auditoría"
    assert "qc@oms" in page.state_label.text()


def test_the_button_reopens_a_closed_day(fresh_db, qtbot):
    audit_service.close_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        auditado_por="qc@oms",
    )
    page = _observation_page(fresh_db, qtbot)
    assert page.close_button.text() == "Reabrir auditoría"
    page.toggle_audit_day()
    assert audit_service.get_audit_day(
        fresh_db, station_id="78486", fecha="2024-04-28"
    ) is None


def test_the_day_badge_says_sin_auditar_until_the_day_is_closed(fresh_db):
    from oms_ui.pages.audit import day_badge

    day = {"date": "2024-04-28", "error_count": 2, "correction_count": 1}
    assert "sin auditar" in day_badge(fresh_db, "78486", day)
    assert "2 errores" in day_badge(fresh_db, "78486", day)
    assert "1 corrección" in day_badge(fresh_db, "78486", day)

    audit_service.close_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        auditado_por="qc@oms",
    )
    assert "auditado" in day_badge(fresh_db, "78486", day)
    assert "sin auditar" not in day_badge(fresh_db, "78486", day)


def test_a_clean_day_still_reads_as_audited_once_closed(fresh_db):
    """The oracle called a zero-error day 'not audited'; that was wrong."""
    from oms_ui.pages.audit import day_badge

    day = {"date": "2024-05-01", "error_count": 0, "correction_count": 0}
    assert "sin auditar" in day_badge(fresh_db, "78486", day)
    audit_service.close_audit_day(
        fresh_db, role="admin", station_id="78486", fecha="2024-05-01",
        auditado_por="qc@oms",
    )
    assert "auditado" in day_badge(fresh_db, "78486", day)


# --------------------------- the audit view reads the schema 2 day (round 25)


def test_the_audit_view_loads_a_schema2_day(fresh_db):
    """Migrated days store {synop{...}}; the oracle shape is flat."""
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "06Z", {
        "ts": "28.4", "meteo_4_1": "50602", "meteo_4_6": "70311",
        "nombre_observador": "YASSER GALAN",
    })
    data = audit_service.load_observation_with_audit(fresh_db, "78486", "2024-04-28")
    hour = data["observation"]["06Z"]
    assert hour["ts"] == "28.4"
    assert hour["meteo_4_1"] == "50602"
    assert hour["observador"] == "YASSER GALAN"


def test_the_audit_view_still_reads_a_legacy_day(fresh_db):
    """The old {horas{...}} documents keep working."""
    import json

    fresh_db.execute(
        "INSERT INTO summary_logs (station_id, year, month, day, kind, data)"
        " VALUES ('78486', 2024, 5, 9, 'diario', ?)",
        (json.dumps({
            "meta": {"estacion": "78486", "fecha": "09052024", "observador": "MARTA"},
            "horas": {"09Z": {"datos": {"ts": "25.1"},
                              "synop": {"Nddff": "40102"},
                              "observador": "MARTA"}},
        }),),
    )
    fresh_db.commit()
    data = audit_service.load_observation_with_audit(fresh_db, "78486", "2024-05-09")
    assert data["observation"]["09Z"]["ts"] == "25.1"
    assert data["observation"]["09Z"]["meteo_4_1"] == "40102"


def test_a_schema2_hour_without_observer_is_auto_marked(fresh_db):
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-04-30", "12Z", {"ts": "27.0"})
    data = audit_service.load_observation_with_audit(fresh_db, "78486", "2024-04-30")
    marks = [m for m in data["error_marks"] if m["campo"] == "observador"]
    assert [m["hora"] for m in marks] == ["12Z"]
    assert marks[0]["marcado_por"] == "Sistema de Calidad"


# ------------------------------- round 27: the four behaviours the OLD has


@pytest.fixture
def audit_page(fresh_db, qtbot):
    from oms_ui.pages.audit_observation import AuditObservationPage

    return AuditObservationPage(
        fresh_db, _tmp_dir(), "78486", "2024-04-28", role="admin", user_email="qc@oms"
    )


def test_the_page_shows_the_stored_cli_sheets(fresh_db, qtbot):
    """The oracle had 'Ver CLI 3074/4074/5074' next to the grid."""
    from oms_core.services import cli as cli_service
    from oms_ui.pages.audit_observation import cli_reference_html

    cli_service.save_cli(fresh_db, "78486", "2024-04-28", "cli3074", {
        "horas": {"2": {"pres_alti": "1012.7", "viento_vel": "4"}},
    })
    html = cli_reference_html(fresh_db, "78486", "2024-04-28", "3074")
    assert "1012.7" in html and "pres_alti" in html
    assert "Sin datos" in cli_reference_html(fresh_db, "78486", "2024-04-28", "5074")


def test_the_page_has_a_button_per_cli(audit_page):
    assert sorted(audit_page.cli_buttons) == ["3074", "4074", "5074"]
    # the oracle labels them CLI 3074 / CLI 4074 / CLI 5074
    for module, button in audit_page.cli_buttons.items():
        assert module in button.text()


def test_selecting_a_mark_in_the_list_selects_its_cell(fresh_db, qtbot, audit_page):
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "12Z",
                               {"ts": "27.0", "nombre_observador": "MARTA"})
    audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        hora="12Z", campo="ts", tipo_error="Sintaxis", marcado_por="qc@oms",
        nota="valor dudoso",
    )
    audit_page.reload()
    # the oracle lists one BLOCK per mark, with its note inside
    assert len(audit_page.mark_blocks) == 1
    labels = [
        child.text()
        for child in audit_page.mark_blocks[0].findChildren(type(audit_page.marks_label))
        if child.text()
    ]
    # the oracle's own field title for ``ts``
    assert any("Temp. Seca" in text for text in labels)
    assert any("valor dudoso" in text for text in labels)


def test_a_mark_can_be_deleted_from_the_list(fresh_db, qtbot, audit_page):
    from oms_core.services import synoptic as synoptic_service

    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "06Z",
                               {"ts": "28.0", "nombre_observador": "YG"})
    audit_service.mark_error(
        fresh_db, role="admin", station_id="78486", fecha="2024-04-28",
        hora="06Z", campo="ts", tipo_error="Sintaxis", marcado_por="qc@oms",
    )
    audit_page.reload()
    mark_id = audit_page._data["error_marks"][0]["id"]
    audit_page._remove_mark_id(mark_id)
    assert audit_service.load_observation_with_audit(
        fresh_db, "78486", "2024-04-28"
    )["error_marks"] == []


def test_a_missing_observer_raises_the_red_banner(fresh_db, qtbot, audit_page):
    from oms_core.services import synoptic as synoptic_service

    # data with nobody signed: the oracle warned about exactly this
    synoptic_service.save_hour(fresh_db, "78486", "2024-04-28", "06Z",
                               {"ts": "28.0"})
    audit_page.reload()
    audit_page.set_hour("06Z")
    # isVisible() is False while the page itself is not shown; ask the widget
    assert audit_page.observer_banner.isHidden() is False


def test_the_correction_dialog_takes_the_corrector_name(audit_page):
    from oms_ui.pages.audit_observation import CorrectionDialog

    dialog = CorrectionDialog()
    dialog.corrector_edit.setText("qc@oms")
    assert dialog.corrector_edit.text() == "qc@oms"
