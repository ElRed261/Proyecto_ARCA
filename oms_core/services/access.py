"""access — page permission matrix and data scope per role (PRD F3).

Mirrors the OLD frontend:

- ``shared/components/Sidebar.jsx`` MODULES role filter, EXCEPT audit which
  follows the stricter App.jsx RoleRoute guard (admin + control_calidad;
  encargado denied — F6-D1, enforced boundary). Seguridad/admin = admin +
  administrador; every other page is visible to all roles);
- dashboard scope rule (§9 rule 5): admin/control_calidad see all stations,
  the other roles are locked to their assigned station.
"""

from __future__ import annotations

from oms_core.services.auth import normalize_role

#: Pages of the main window (Sidebar MODULES ids).
PAGES = ("dashboard", "synoptic", "summary", "audit", "maintenance",
         "transform", "admin")

#: Roles required per page; ``None`` means visible to every role.
#:
#: ``audit`` follows the ENFORCED App.jsx RoleRoute guard
#: (admin + control_calidad only), NOT the wider Sidebar.jsx MODULES list
#: that also admitted encargado. See Migración/evidencias/F6/NOTA.md
#: (F6-D1): keep-deny is the default; opening to encargado needs the
#: user's explicit call.
_PAGE_ROLES: dict[str, tuple[str, ...] | None] = {
    "dashboard": None,
    "synoptic": None,
    "summary": None,
    "audit": ("admin", "control_calidad"),
    "maintenance": None,
    "transform": ("admin",),
    "admin": ("admin",),
}

#: Roles with global (all-station) scope — §9 rule 5.
_GLOBAL_ROLES = frozenset({"admin", "control_calidad"})


def can_access(role: str, page: str) -> bool:
    """True when ``role`` may open ``page`` (Sidebar matrix)."""
    required = _PAGE_ROLES.get(page, ())
    if page not in PAGES:
        return False
    if required is None:
        return True
    return normalize_role(role) in {normalize_role(r) for r in required}


def scope_for(role: str, assigned_station: str | None) -> str:
    """'all' for global roles, otherwise the assigned station id.

    A non-global role without an assigned station is denied with a clear
    error — silently returning an empty scope would hide data.
    """
    if normalize_role(role) in _GLOBAL_ROLES:
        return "all"
    if assigned_station is None:
        raise PermissionError(
            f"Sin estación asignada: el rol '{role}' requiere una estación asignada"
        )
    return assigned_station
