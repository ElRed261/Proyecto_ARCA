"""A10 — the session token lives in the OS keyring, with a logged fallback.

A bearer token is a secret: plain text in QSettings is the wrong place. Not
every machine has a usable keyring (containers, headless Linux), so the
fallback keeps the app working instead of blocking the login.
"""

import pytest

from oms_ui import startup


class _FakeKeyring:
    """Minimal in-memory stand-in for the keyring API."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, account, value):
        self.store[(service, account)] = value

    def get_password(self, service, account):
        return self.store.get((service, account))

    def delete_password(self, service, account):
        self.store.pop((service, account), None)


class _BrokenKeyring:
    def set_password(self, *a, **k):
        raise RuntimeError("sin llavero")

    def get_password(self, *a, **k):
        raise RuntimeError("sin llavero")

    def delete_password(self, *a, **k):
        raise RuntimeError("sin llavero")


@pytest.fixture()
def qsettings(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    yield
    startup.clear_token()


def test_the_token_goes_to_the_keyring(monkeypatch, qsettings):
    fake = _FakeKeyring()
    monkeypatch.setattr(startup, "_keyring", lambda: fake)
    startup.save_token("abc123")
    assert fake.store[(startup.SERVICE_NAME, startup.ACCOUNT_NAME)] == "abc123"
    assert startup.load_token() == "abc123"


def test_clearing_removes_it_everywhere(monkeypatch, qsettings):
    fake = _FakeKeyring()
    monkeypatch.setattr(startup, "_keyring", lambda: fake)
    startup.save_token("abc123")
    startup.clear_token()
    assert startup.load_token() == ""


def test_a_broken_keyring_falls_back_to_qsettings(monkeypatch, qsettings):
    monkeypatch.setattr(startup, "_keyring", lambda: _BrokenKeyring())
    startup.save_token("respaldo")
    assert startup.load_token() == "respaldo"  # read back through the fallback


def test_a_missing_keyring_also_falls_back(monkeypatch, qsettings):
    monkeypatch.setattr(startup, "_keyring", lambda: None)
    startup.save_token("sin-llavero")
    assert startup.load_token() == "sin-llavero"


def test_a_keyring_token_wins_over_the_stale_settings_copy(monkeypatch, qsettings):
    fake = _FakeKeyring()
    monkeypatch.setattr(startup, "_keyring", lambda: fake)
    startup.settings().setValue(startup._TOKEN_KEY, "viejo")
    fake.set_password(startup.SERVICE_NAME, startup.ACCOUNT_NAME, "nuevo")
    assert startup.load_token() == "nuevo"
