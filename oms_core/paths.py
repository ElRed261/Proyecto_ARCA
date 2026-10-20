"""Path resolution chain — port of ``OLD .../paths_config.rs`` (P1.2/P1.4).

Resolution order for the offline root (the layer ``{modulo}`` is always kept):

1. ``ARCA_BASE_DIR`` environment variable (tests / advanced installs).
2. ``offline_root`` of the PathProfile stored in ``app_config`` under the
   ``path_config`` key (configured by the admin).
3. Platform default ``Documents/OMS``.

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
import sys
from pathlib import Path

from oms_core.db.repositories import app_config
from oms_core.db.repositories.app_config import set as _kv_set

#: Name of the env var override for tests/advanced installations.
ENV_BASE_DIR = "ARCA_BASE_DIR"

#: Env override for the per-user data directory (dev, CI, portable installs).
ENV_DATA_DIR = "OMS_DATA_DIR"

#: Identity used by platformdirs to build the per-OS data directory.
APP_NAME = "oms"
APP_AUTHOR = "NeoArca"

#: File name of the SQLite database inside the data directory.
DATABASE_NAME = "oms.db"

#: app_config key where the serialised PathProfile lives.
PATH_CONFIG_KEY = "path_config"

#: Default module layer appended to the resolved root (SYNOP_MODULE port).
DEFAULT_MODULE = "synop"

#: Sections created inside the resolved root, in display order. The tree is
#: ``{root}/{section}/<ESTACION>/<AÑO>/<MES>/`` for the two record sections
#: and a flat ``{root}/{section}/`` for the two archive sections.
SECTION_SYNOP = "synop"
SECTION_SUMMARIES = "resumenes"
SECTION_EXPORTS = "exportaciones"
SECTION_BACKUPS = "respaldos"
SECTIONS: tuple[str, ...] = (
    SECTION_SYNOP, SECTION_SUMMARIES, SECTION_EXPORTS, SECTION_BACKUPS,
)


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

    offline_root == "" means "not configured" -> default Documents/OMS.
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


def _documents_dir(
    home: str, env: dict[str, str] | None = None, *, platform: str | None = None
) -> Path:
    """The user's Documents folder, localized when the desktop says so.

    A Spanish desktop keeps it at ``~/Documentos`` and records that in
    ``user-dirs.dirs`` (``XDG_DOCUMENTS_DIR``). Defaulting to a hardcoded
    ``Documents`` would silently create a second, parallel folder on those
    machines, so the XDG value wins and ``Documents`` is only the fallback.
    """
    env_map = os.environ if env is None else env
    explicit = (env_map.get("XDG_DOCUMENTS_DIR") or "").strip()
    if explicit:
        return Path(os.path.expanduser(explicit))

    config_home = env_map.get("XDG_CONFIG_HOME") or str(Path(home) / ".config")
    try:
        lines = (Path(config_home) / "user-dirs.dirs").read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    plat = (platform or sys.platform).lower()
    if plat.startswith("win"):
        # Windows often redirects Documents into OneDrive; prefer the real one.
        for key in ("OneDrive", "USERPROFILE"):
            base = (env_map.get(key) or "").strip()
            if not base:
                continue
            candidate = Path(base) / "Documents"
            if candidate.is_dir():
                return candidate
        return Path(home) / "Documents"

    for line in lines:
        key, _, raw = line.partition("=")
        if key.strip() != "XDG_DOCUMENTS_DIR":
            continue
        value = raw.strip().strip('"')
        if not value:
            break
        return Path(value.replace("$HOME", home))
    return Path(home) / "Documents"


def data_dir(env: dict[str, str] | None = None, *, platform: str | None = None) -> Path:
    """Per-user data directory for the database — ``platformdirs`` decides.

    Linux: ``$XDG_DATA_HOME/oms`` (``~/.local/share/oms``) · Windows:
    ``%LOCALAPPDATA%\\NeoArca\\oms`` · macOS: ``~/Library/Application
    Support/oms``. ``OMS_DATA_DIR`` overrides everything (development, CI or a
    portable install), and ``platform`` is injectable so every branch has a
    test on a single host.

    The database must NOT live in Documents: a synced folder (Drive, OneDrive)
    breaks SQLite's locking. The JSON tree is what goes there.
    """
    env_map = os.environ if env is None else env
    override = (env_map.get(ENV_DATA_DIR) or "").strip()
    if override:
        return Path(os.path.expanduser(override))
    plat = (platform or sys.platform).lower()
    if plat.startswith("win"):
        from platformdirs.windows import Windows as _platform
    elif plat.startswith(("darwin", "mac")):
        from platformdirs.macos import MacOS as _platform
    else:
        from platformdirs.unix import Unix as _platform
    return Path(_platform(APP_NAME, APP_AUTHOR).user_data_dir)


def database_path(
    env: dict[str, str] | None = None, *, platform: str | None = None
) -> Path:
    """Where the application database lives on this machine."""
    return data_dir(env, platform=platform) / DATABASE_NAME


def default_documents_root(env: dict[str, str] | None = None) -> Path:
    """Platform default root: the localized Documents folder + ``OMS``."""
    env_map = os.environ if env is None else env
    home = env_map.get("HOME") or str(Path.home())
    return _documents_dir(home, env_map, platform=env_map.get("OMS_PLATFORM")) / "OMS"


def section_dir(root: str | Path, section: str) -> Path:
    """``{root}/{section}`` — the section names are a closed set."""
    if section not in SECTIONS:
        raise PathConfigError(
            f"sección de rutas desconocida: '{section}'"
            f" (válidas: {', '.join(SECTIONS)})"
        )
    return Path(root) / section


def ensure_directories(
    conn: sqlite3.Connection,
    *,
    section: str | None = None,
    env: dict[str, str] | None = None,
    default_root: str | None = None,
    modulo: str = "",
) -> Path:
    """Create the section tree under the resolved ROOT and return that root.

    The sections live beside each other (``OMS/synop``, ``OMS/resumenes``, …),
    never inside the module layer: letting the module layer in here would nest
    them as ``OMS/synop/synop``.

    Pure side effect of existence: never deletes, never overwrites, and an
    unwritable root propagates the OSError so the caller can report it
    honestly instead of pretending the layout exists.
    """
    root = offline_base_dir(
        conn, env=env, default_root=default_root, modulo=modulo)
    targets = SECTIONS if section is None else (section,)
    for name in targets:
        section_dir(root, name).mkdir(parents=True, exist_ok=True)
    return root


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
        default_root if default_root is not None
        else str(default_documents_root(env_map))
    )
    return resolve_offline_root(
        None,
        profile.offline_root if profile is not None else None,
        resolved_default,
        modulo,
    )
