"""A4 — the day closes at 06Z of the next day (02:00 local), rule R4."""

import datetime as dt

import pytest

from oms_core.services import closure

FECHA = "2025-10-26"


def test_the_closing_moment_is_next_day_02_local():
    assert closure.closing_moment(FECHA) == dt.datetime(2025, 10, 27, 2, 0)


def test_the_day_is_open_until_the_closing_moment():
    assert closure.is_closed(FECHA, now=dt.datetime(2025, 10, 26, 23, 59)) is False
    assert closure.is_closed(FECHA, now=dt.datetime(2025, 10, 27, 1, 59)) is False


def test_the_day_is_closed_from_the_closing_moment_on():
    assert closure.is_closed(FECHA, now=dt.datetime(2025, 10, 27, 2, 0)) is True
    assert closure.is_closed(FECHA, now=dt.datetime(2025, 10, 28, 12, 0)) is True


@pytest.mark.parametrize("role", ["observador", "digitador", "", None])
def test_a_closed_day_refuses_regular_roles(role):
    now = dt.datetime(2025, 10, 27, 9, 0)
    assert closure.can_edit(role, FECHA, now=now) is False


@pytest.mark.parametrize("role", ["admin", "control_calidad"])
def test_correcting_roles_may_still_open_a_closed_day(role):
    now = dt.datetime(2025, 10, 27, 9, 0)
    assert closure.can_edit(role, FECHA, now=now) is True


def test_an_open_day_accepts_every_role():
    now = dt.datetime(2025, 10, 26, 18, 0)
    assert closure.can_edit("observador", FECHA, now=now) is True


def test_every_edit_of_a_closed_day_needs_justification():
    now = dt.datetime(2025, 10, 27, 9, 0)
    assert closure.needs_justification("admin", FECHA, now=now) is True
    assert closure.needs_justification("admin", FECHA,
                                       now=dt.datetime(2025, 10, 26, 18, 0)) is False


def test_the_message_names_the_day_and_the_rule():
    message = closure.closed_message(FECHA)
    assert FECHA in message
    assert "06Z" in message
    assert "justificación" in message
