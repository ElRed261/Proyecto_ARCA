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
