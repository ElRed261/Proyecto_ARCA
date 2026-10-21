"""F3 — access matrix tests, mirroring OLD frontend Sidebar.jsx MODULES +
auth.js role normalization, and §9 rule 5 (observer locked to its station)."""

import pytest

from oms_core.services import access

ROLES = ["admin", "control_calidad", "encargado", "observador"]
PAGES = ["dashboard", "synoptic", "audit", "summary", "maintenance", "admin"]

# F6-D1 enforced boundary: audit follows the App.jsx RoleRoute guard
# (admin + control_calidad only), NOT the wider Sidebar.jsx MODULES list that
# also admitted encargado. See Migración/evidencias/F6/NOTA.md.
EXPECTED = {
    "admin": {p: True for p in PAGES},
    "control_calidad": {
        "dashboard": True,
        "synoptic": True,
        "summary": True,
        "audit": True,
        "maintenance": True,
        "admin": False,
    },
    "encargado": {
        "dashboard": True,
        "synoptic": True,
        "summary": True,
        "audit": False,
        "maintenance": True,
        "admin": False,
    },
    "observador": {
        "dashboard": True,
        "synoptic": True,
        "summary": True,
        "audit": False,
        "maintenance": True,
        "admin": False,
    },
}


def test_full_permission_matrix_4_roles_x_6_pages():
    for role in ROLES:
        for page in PAGES:
            assert access.can_access(role, page) is EXPECTED[role][page], f"{role} x {page}"


def test_administrador_alias_tiene_los_mismos_accesos_que_admin():
    for page in PAGES:
        assert access.can_access("administrador", page) is EXPECTED["admin"][page]
        assert access.can_access("ADMINISTRADOR", page) is EXPECTED["admin"][page]


def test_roles_normalizados_en_mayusculas():
    assert access.can_access("OBSERVADOR", "audit") is False
    assert access.can_access("ENCARGADO", "audit") is False  # F6-D1 enforced


def test_pagina_desconocida_se_deniega():
    for role in ROLES:
        assert access.can_access(role, "no-existe") is False


# ---------------------------------------------------------------- scope


def test_scope_all_para_admin_y_control_calidad():
    assert access.scope_for("admin", None) == "all"
    assert access.scope_for("administrador", "78451") == "all"
    assert access.scope_for("control_calidad", None) == "all"


def test_scope_estacion_asignada_para_encargado_y_observador():
    assert access.scope_for("encargado", "78451") == "78451"
    assert access.scope_for("observador", "78485") == "78485"


def test_scope_sin_estacion_asignada_deniega_con_error_claro():
    for role in ("encargado", "observador"):
        with pytest.raises(PermissionError) as excinfo:
            access.scope_for(role, None)
        assert "asignada" in str(excinfo.value)
