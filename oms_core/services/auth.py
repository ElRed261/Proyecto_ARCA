"""auth — users, sessions, roles (PRD F3).

Verbatim port of the observable contract of
``OLD frontend/src-tauri/src/modules/auth/mod.rs``:

- bcrypt password hashing with ``DEFAULT_COST`` (12);
- a constant dummy-hash bcrypt verify on unknown emails so the login timing
  cannot enumerate users;
- in-memory session store with 8h expiry, sweep on login and logout;
- ``require_role`` raising :class:`PermissionError` with the oracle message;
- role normalization (lowercase, ``'administrador'`` -> ``'admin'``) matching
  the frontend ``shared/utils/auth.js``;
- ``seed_admin`` first-run seeding of the four default users plus the
  ``primer_inicio.txt`` marker file (``OLD .../db.rs::init_db``).

Pure Python, no Qt (ADR-03).
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import bcrypt

import oms_core.db.repositories.users as users_repo

#: Sessions expire after 8 hours (oracle ``SESSION_TTL_SECS``).
SESSION_TTL_SECS = 28800

#: bcrypt cost used by the oracle (``bcrypt::DEFAULT_COST``).
DEFAULT_BCRYPT_COST = 12

#: Fixed password hashed ONLY to equalize the response time of the
#: "unknown email" path, so login timing cannot enumerate users.
_DUMMY_PASSWORD = "arca-timing-equalizer"

_dummy_hash_lock = threading.Lock()
_dummy_hash_cache: str | None = None


class AuthError(Exception):
    """Raised for invalid credentials, disabled accounts and bad sessions."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=DEFAULT_BCRYPT_COST)
    ).decode("ascii")


def verify(password: str, password_hash: str) -> bool:
    """bcrypt check. Kept as a module-level function so tests can spy on it."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def dummy_password_hash() -> str:
    """Constant bcrypt hash used only for timing equalization (lazy, cached)."""
    global _dummy_hash_cache
    if _dummy_hash_cache is None:
        with _dummy_hash_lock:
            if _dummy_hash_cache is None:
                _dummy_hash_cache = hash_password(_DUMMY_PASSWORD)
    return _dummy_hash_cache


def normalize_role(role: str | None) -> str:
    """Lowercase role with the frontend 'administrador' alias of 'admin'."""
    if not role:
        return ""
    normalized = role.strip().lower()
    if normalized == "administrador":
        return "admin"
    return normalized


@dataclass(frozen=True)
class Session:
    user_id: int
    email: str
    role: str
    created_at: int


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    token_type: str
    user_email: str
    role: str

    @property
    def roles(self) -> list[str]:
        return [self.role]


class SessionStore:
    """In-memory token -> Session map, mirroring the oracle ``SessionStore``."""

    def __init__(self, clock: Callable[[], int] | None = None) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._clock: Callable[[], int] = clock or (lambda: int(time.time()))

    def create_session(self, user_id: int, email: str, role: str) -> str:
        # Session token = 32 bytes of the OS CSPRNG, hex (64 chars).
        token = secrets.token_hex(32)
        session = Session(
            user_id=user_id, email=email, role=role, created_at=self._clock()
        )
        with self._lock:
            self._sessions[token] = session
        return token

    def validate_session(self, token: str) -> Session:
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                raise AuthError("Sesión no encontrada o inválida")
            if self._clock() - session.created_at > SESSION_TTL_SECS:
                # Remove the expired entry: the store must not grow unbounded.
                del self._sessions[token]
                raise AuthError("Sesión expirada")
            return session

    def sweep_expired(self) -> None:
        """Remove all expired sessions. Called on every login to bound growth."""
        now = self._clock()
        with self._lock:
            expired = [t for t, s in self._sessions.items() if now - s.created_at > SESSION_TTL_SECS]
            for token in expired:
                del self._sessions[token]

    def delete_session(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)


def login(
    conn, session_store: SessionStore, email: str, password: str
) -> LoginResult:
    """Authenticate a user against the users table (oracle login_user_logic)."""
    user = users_repo.get_user_by_email(conn, email)
    if user is None:
        # Equalize the cost of the "wrong password" path (one bcrypt verify
        # against a constant hash) so timing cannot enumerate users.
        verify(password, dummy_password_hash())
        raise AuthError("Usuario o contraseña incorrectos")

    if not user.is_active:
        raise AuthError("La cuenta de usuario está desactivada")

    if not verify(password, user.password_hash):
        raise AuthError("Usuario o contraseña incorrectos")

    # Sweep expired sessions on every login to bound store growth.
    session_store.sweep_expired()

    access_token = session_store.create_session(user.id, user.email, user.role)
    return LoginResult(
        access_token=access_token,
        token_type="bearer",
        user_email=user.email,
        role=user.role,
    )


def logout(session_store: SessionStore, token: str) -> str:
    session_store.delete_session(token)
    return "Sesión cerrada"


def require_role(
    session_store: SessionStore, token: str, allowed_roles: list[str] | tuple[str, ...]
) -> Session:
    """Validate the token and enforce one of the allowed roles.

    Role comparison is done over :func:`normalize_role` so the frontend alias
    'administrador' satisfies ['admin'] (oracle require_role contract).
    """
    session = session_store.validate_session(token)
    allowed = {normalize_role(r) for r in allowed_roles}
    if normalize_role(session.role) not in allowed:
        raise PermissionError("No autorizado: privilegios insuficientes")
    return session


_SEED_USERS = (
    ("admin@arca.rd", "admin"),
    ("encargado@arca.rd", "encargado"),
    ("observador@arca.rd", "observador"),
    ("calidad@arca.rd", "control_calidad"),
)

# Same alphabet the oracle used (no ambiguous 0/O/1/l/I), 12 chars.
_SEED_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_seed_password() -> str:
    # The oracle used a xorshift PRNG seeded with the clock; the CSPRNG of the
    # OS is the honest equivalent (same alphabet and length) — NOTA F3 D3.
    return "".join(secrets.choice(_SEED_ALPHABET) for _ in range(12))


def seed_admin(conn, seed_dir) -> dict[str, str] | None:
    """Seed the four default users on an empty users table and write the
    ``primer_inicio.txt`` credentials file (oracle ``db.rs::init_db``).

    Idempotent: returns ``None`` and touches nothing when users already exist.
    """
    if users_repo.count_users(conn) > 0:
        return None

    credentials: dict[str, str] = {}
    for email, role in _SEED_USERS:
        password = _generate_seed_password()
        users_repo.add_user(
            conn, email, hash_password(password), role, is_active=True
        )
        credentials[email] = password

    content = (
        "=== CREDENCIALES DE PRIMER INICIO PARA PROYECTO ARCA ===\n\n"
        + "".join(f"{email} : {credentials[email]}\n" for email, _ in _SEED_USERS)
        + "\nIMPORTANTE: Por razones de seguridad, cambie estas contraseñas"
        " inmediatamente en el panel de administración.\n"
    )
    (seed_dir / "primer_inicio.txt").write_text(content, encoding="utf-8")
    # Spec S3: the file holds working passwords, so nobody else on the machine
    # may read it.
    (seed_dir / "primer_inicio.txt").chmod(0o600)
    return credentials


# Re-export so UI/core callers can create users with the hashing policy here.
add_user = users_repo.add_user
