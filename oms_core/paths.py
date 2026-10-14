"""Path resolution chain — port of ``OLD .../paths_config.rs`` (P1.2/P1.4).

Resolution order for the offline root (the layer ``{modulo}`` is always kept):

1. ``ARCA_BASE_DIR`` environment variable (tests / advanced installs).
2. ``offline_root`` of the PathProfile stored in ``app_config`` under the
   ``path_config`` key (configured by the admin).
3. Platform default ``Documents/ARCA``.

Failure policy (P1.4 hard-fail): a corrupt or unreadable PathProfile raises
:class:`PathConfigError`. We NEVER silently fall back to the default —
writing into the wrong place is equivalent to losing data.

The user-facing error strings mirror the Rust oracle verbatim so the
maintenance panel keeps behaving identically.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from oms_core.db.repositories import app_config
from oms_core.db.repositories.app_config import set as _kv_set

#: Name of the env var override for tests/advanced installations.
ENV_BASE_DIR = "ARCA_BASE_DIR"

#: app_config key where the serialised PathProfile lives.
PATH_CONFIG_KEY = "path_config"

#: Default module layer appended to the resolved root (SYNOP_MODULE port).
DEFAULT_MODULE = "synop"


class PathConfigError(Exception):
    """A PathProfile is invalid or corrupt, or the config store is unreadable."""


def _is_absolute(p: str) -> bool:
    """Port of es_ruta_absoluta: Windows ``C:\\...``/``D:/...`` or Unix leading ``/``."""
    if p.startswith("/"):
        return True
    b = p.encode()
    return len(b) >= 3 and chr(b[0]).isascii() and chr(b[0]).isalpha() and b[1:2] == b":" and b[2:3] in (b"\\", b"/")


def _normalize_comparable(p: str) -> str:
    """Port of normalizar: no trailing slashes, case-insensitive first char."""
    trimmed = p.rstrip("/\\")
    if len(trimmed) >= 2:
        return trimmed[0].lower() + trimmed[1:]
    return trimmed


# --------------------------------------------------------------------------
# PathProfile
# --------------------------------------------------------------------------


def _path_profile_from_dict(data: dict) -> PathProfile:
    """Build a profile from parsed JSON (serde semantics: unknown keys are
    ignored; wrong field types make the stored profile corrupt)."""
    try:
        offline_root = data.get("offline_root", "")
        online_root = data.get("online_root")
        backups = data.get("backups_max_age_days")
        summaries = data.get("summaries_dir")
        if not isinstance(offline_root, str):
            raise TypeError("offline_root must be a string")
        if online_root is not None and not isinstance(online_root, str):
            raise TypeError("online_root must be a string")
        if backups is not None and not isinstance(backups, int):
            raise TypeError("backups_max_age_days must be an integer")
        if summaries is not None and not isinstance(summaries, str):
            raise TypeError("summaries_dir must be a string")
    except TypeError as exc:
        raise PathConfigError(f"path_config corrupto: {exc}") from exc
    return PathProfile(
        offline_root=offline_root,
        online_root=online_root,
        backups_max_age_days=backups,
        summaries_dir=summaries,
    )


class PathProfile:
    """Serialised path profile (mirror of the Rust serde struct).

    offline_root == "" means "not configured" -> default Documents/ARCA.
    """

    __slots__ = ("backups_max_age_days", "offline_root", "online_root", "summaries_dir")

    def __init__(
        self,
        offline_root: str = "",
        online_root: str | None = None,
        backups_max_age_days: int | None = None,
        summaries_dir: str | None = None,
    ) -> None:
        self.offline_root = offline_root
        self.online_root = online_root
        self.backups_max_age_days = backups_max_age_days
        self.summaries_dir = summaries_dir

    def to_dict(self) -> dict:
        return {
            "offline_root": self.offline_root,
            "online_root": self.online_root,
            "backups_max_age_days": self.backups_max_age_days,
            "summaries_dir": self.summaries_dir,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PathProfile):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"PathProfile({self.to_dict()!r})"


def validate_profile(profile: PathProfile) -> None:
    """Port of the pure Rust validate_profile (same rules, same messages)."""
    if profile.offline_root and not _is_absolute(profile.offline_root):
        raise PathConfigError(
            f"offline_root debe ser una ruta absoluta (se recibió '{profile.offline_root}')"
        )

    if profile.online_root is not None:
        online = profile.online_root
        if online == "":
            raise PathConfigError("online_root, si se define, no puede ser vacío")
        if not _is_absolute(online):
            raise PathConfigError(
                f"online_root debe ser una ruta absoluta (se recibió '{online}')"
            )
        if profile.offline_root and _normalize_comparable(online) == _normalize_comparable(
            profile.offline_root
        ):
            raise PathConfigError(
                "online_root y offline_root no pueden apuntar a la misma carpeta: "
                "se perdería la separación local/online y el conflicto por Drive sync"
            )

    if profile.summaries_dir is not None and profile.summaries_dir != "":
        summaries = profile.summaries_dir
        if not _is_absolute(summaries):
            raise PathConfigError(
                f"summaries_dir debe ser una ruta absoluta (se recibió '{summaries}')"
            )
        if profile.offline_root and _normalize_comparable(summaries) == _normalize_comparable(
            profile.offline_root
        ):
            raise PathConfigError(
                "summaries_dir no puede coincidir con offline_root: los resúmenes son "
                "documentos de distinto ciclo de vida que las observaciones crudas"
            )


def default_offline_only(offline_root: str) -> PathProfile:
    """Offline-only profile (Rust PathProfile::default_offline_only)."""
    return PathProfile(offline_root=offline_root)


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------


def get_path_profile(conn: sqlite3.Connection) -> PathProfile | None:
    """Read the PathProfile from app_config (None if never configured).

    A stored, unparsable JSON is a hard error (P1.4): never fall back silently.
    """
    value = app_config.get(conn, PATH_CONFIG_KEY)
    if value is None:
        return None
    try:
        data = json.loads(value)
    except ValueError as exc:
        raise PathConfigError(f"path_config corrupto: {exc}") from exc
    if not isinstance(data, dict):
        raise PathConfigError(f"path_config corrupto: expected JSON object, got {type(data).__name__}")
    return _path_profile_from_dict(data)


def set_path_profile(conn: sqlite3.Connection, profile: PathProfile) -> None:
    """Validate and persist the profile (Rust set_path_config_db, no role check:
    role enforcement belongs to F3 auth)."""
    validate_profile(profile)
    try:
        serialised = json.dumps(profile.to_dict())
    except (TypeError, ValueError) as exc:  # pragma: no cover - dataclass of scalars
        raise PathConfigError(f"path_config no serializable: {exc}") from exc
    _kv_set(conn, PATH_CONFIG_KEY, serialised)


# --------------------------------------------------------------------------
# resolution chain
# --------------------------------------------------------------------------


def default_documents_root() -> Path:
    """Platform default: ``Documents/ARCA`` (with the historical HOME fallback)."""
    home = os.environ.get("HOME") or str(Path.home())
    return Path(home) / "Documents" / "ARCA"


def resolve_offline_root(
    env_base: str | None,
    profile_offline_root: str | None,
    default_root: str,
    modulo: str,
) -> Path:
    """Pure P1.2 chain: env > profile > default, ``{modulo}`` layer preserved."""
    if env_base:
        return Path(env_base) / modulo
    if profile_offline_root:
        return Path(profile_offline_root) / modulo
    return Path(default_root) / modulo


def offline_base_dir(
    conn: sqlite3.Connection,
    *,
    env: dict[str, str] | None = None,
    default_root: str | None = None,
    modulo: str = DEFAULT_MODULE,
) -> Path:
    """Resolve the real offline root for a connection.

    ``env`` defaults to ``os.environ`` and is injectable for tests.
    Deviation (documented in Migración/evidencias/F1/NOTA.md): an env var
    that is set but empty is ignored here, whereas the Rust wrapper would
    skip straight past profile AND default and end up with a relative
    {'modulo'} directory — exactly the write-in-the-wrong-place failure this
    module exists to prevent.
    """
    env_map = os.environ if env is None else env
    env_base = env_map.get(ENV_BASE_DIR)
    if env_base:
        return resolve_offline_root(env_base, None, default_root or "", modulo)

    profile = get_path_profile(conn)  # loud on corrupt/unreadable config

    resolved_default = (
        default_root if default_root is not None else str(default_documents_root())
    )
    return resolve_offline_root(
        None,
        profile.offline_root if profile is not None else None,
        resolved_default,
        modulo,
    )
