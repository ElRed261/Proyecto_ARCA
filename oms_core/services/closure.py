"""Day closure (rule R4 of ``docs/ARQUITECTURA_DATOS.md``).

A day's document closes at **06Z of the following day** — 02:00 local time in
the Dominican Republic (UTC-4), which is when the next synoptic cycle starts.
Until then the whole day stays editable; afterwards only the audit roles may
correct it, with a justification that lands in ``document_versions``.

The rule is pure and takes an injectable ``now`` so the window is testable
without waiting for the clock.
"""

from __future__ import annotations

import datetime as _dt

#: 06Z is the first hour of the next synoptic cycle.
CLOSING_HOUR_UTC = 6

#: República Dominicana is UTC-4 all year round (no daylight saving).
LOCAL_UTC_OFFSET_HOURS = -4

#: Roles that may correct a closed day (always with a justification).
CORRECTING_ROLES = frozenset({"admin", "control_calidad"})

#: Message shown when a closed day is edited by a non-correcting role.
CLOSED_MESSAGE = (
    "El día {fecha} se cerró a las 06Z del día siguiente. "
    "Sólo administración o control de calidad pueden corregirlo, "
    "y la corrección queda registrada con justificación."
)


def closing_moment(fecha: str) -> _dt.datetime:
    """Local datetime at which ``fecha`` closes (next day 02:00)."""
    day = _dt.date.fromisoformat(fecha)
    closing_utc = _dt.datetime.combine(
        day + _dt.timedelta(days=1), _dt.time(hour=CLOSING_HOUR_UTC)
    )
    return closing_utc + _dt.timedelta(hours=LOCAL_UTC_OFFSET_HOURS)


def is_closed(fecha: str, *, now: _dt.datetime | None = None) -> bool:
    """True once the closing moment has passed."""
    return (now or _dt.datetime.now()) >= closing_moment(fecha)


def can_edit(
    role: str | None, fecha: str, *, now: _dt.datetime | None = None
) -> bool:
    """An open day is free; a closed one needs a correcting role."""
    if not is_closed(fecha, now=now):
        return True
    return str(role or "") in CORRECTING_ROLES


def needs_justification(
    role: str | None, fecha: str, *, now: _dt.datetime | None = None
) -> bool:
    """Every edit of a closed day is audited, correcting role included."""
    return is_closed(fecha, now=now)


def closed_message(fecha: str) -> str:
    return CLOSED_MESSAGE.format(fecha=fecha)


__all__ = [
    "CLOSED_MESSAGE",
    "CLOSING_HOUR_UTC",
    "CORRECTING_ROLES",
    "can_edit",
    "closed_message",
    "closing_moment",
    "is_closed",
    "needs_justification",
]
