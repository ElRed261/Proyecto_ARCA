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
