"""Startup flow for Neo Arca (PRD F7.5): splash + session restore + login.

Oracle parity (OLD App.jsx): on launch, try the stored token ("Restaurando
sesión…"); a dead token falls back to the login screen. The session store
is in-memory, so restarts always re-login — documented, not a bug.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from oms_core.services.auth import LoginResult, SessionStore

_SETTINGS_ORG = "NeoArca"
_SETTINGS_APP = "shell"
_TOKEN_KEY = "session_token"


def ensure_storage_layout(conn) -> str | None:
    """Create the Documents/OMS section tree; report instead of crashing.

    Returns ``None`` on success or the honest error message, so the shell can
    surface a non-writable root without blocking the login.
    """
    from oms_core import paths as paths_mod

    try:
        paths_mod.ensure_directories(conn)
    except (paths_mod.PathConfigError, OSError) as exc:
        return str(exc)
    return None


def settings() -> QSettings:
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def save_token(token: str) -> None:
    settings().setValue(_TOKEN_KEY, token)


def clear_token() -> None:
    settings().remove(_TOKEN_KEY)


def try_restore_session(store: SessionStore) -> LoginResult | None:
    """Validate the stored token; None when absent, dead or expired."""
    token = settings().value(_TOKEN_KEY, "", type=str)
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
