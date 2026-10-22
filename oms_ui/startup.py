"""Session token storage: the OS keyring first, QSettings as a fallback.

A bearer token in ``QSettings`` is plain text in a config file; the keyring is
where a secret belongs (`keyring` handles Windows Credential Locker, macOS
Keychain and the Linux Secret Service). Not every machine has a working
keyring — a headless Linux box or a container typically does not — so the
fallback keeps the application usable and says so in the log.
"""

from __future__ import annotations

import logging

from oms_core.services.auth import LoginResult, SessionStore

_LOGGER = logging.getLogger(__name__)

#: Service/key names inside the OS keyring.
SERVICE_NAME = "NeoArca-OMS"
ACCOUNT_NAME = "session_token"

_SETTINGS_ORG = "NeoArca"
_SETTINGS_APP = "shell"
_TOKEN_KEY = "session_token"


def _keyring():
    """The keyring module, or ``None`` when the backend is unusable."""
    try:
        import keyring
    except Exception:  # noqa: BLE001 - a missing/broken keyring is not fatal
        return None
    return keyring


def save_token(token: str) -> None:
    """Store the token in the keyring, else in QSettings (logged)."""
    backend = _keyring()
    if backend is not None:
        try:
            backend.set_password(SERVICE_NAME, ACCOUNT_NAME, token)
            settings().remove(_TOKEN_KEY)  # never keep two copies alive
            _LOGGER.info("token guardado en el llavero del sistema")
            return
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("el llavero no está disponible (%s); uso QSettings", exc)
    else:
        _LOGGER.warning("keyring no instalado; el token va a QSettings")
    settings().setValue(_TOKEN_KEY, token)


def clear_token() -> None:
    """Remove the token from both places; nothing to undo is not an error."""
    backend = _keyring()
    if backend is not None:
        try:
            backend.delete_password(SERVICE_NAME, ACCOUNT_NAME)
        except Exception as exc:  # noqa: BLE001 - absent credential or dead backend
            _LOGGER.debug("no se pudo borrar del llavero: %s", exc)
    settings().remove(_TOKEN_KEY)


def load_token() -> str:
    backend = _keyring()
    if backend is not None:
        try:
            token = backend.get_password(SERVICE_NAME, ACCOUNT_NAME)
            if token:
                return str(token)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("el llavero no respondió: %s", exc)
    return str(settings().value(_TOKEN_KEY, "", type=str) or "")


def settings():
    from PySide6.QtCore import QSettings

    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def try_restore_session(store: SessionStore) -> LoginResult | None:
    """Validate the stored token; None when absent, dead or expired."""
    token = load_token()
    if not token:
        return None
    try:
        session = store.validate_session(token)
    except Exception:  # noqa: BLE001 - any dead token means "go to login"
        clear_token()
        return None
    return LoginResult(
        access_token=token,
        token_type="bearer",
        user_email=session.email,
        role=session.role,
    )


def ensure_storage_layout(conn) -> str | None:
    """Create the Documents/OMS section tree; report instead of crashing."""
    from oms_core import paths as paths_mod

    try:
        paths_mod.ensure_directories(conn)
    except (paths_mod.PathConfigError, OSError) as exc:
        return str(exc)
    return None


__all__ = [
    "ACCOUNT_NAME",
    "SERVICE_NAME",
    "clear_token",
    "ensure_storage_layout",
    "load_token",
    "save_token",
    "settings",
    "try_restore_session",
]
