"""F1 paths: resolution chain ARCA_BASE_DIR > PathProfile (app_config KV) >
Documents/ARCA, mirroring OLD paths_config.rs (P1.2 chain + P1.4 hard-fail).

The chain is pure and testable without any GUI/Tauri handle.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from oms_core.paths import (
    ENV_BASE_DIR,
    PATH_CONFIG_KEY,
    PathConfigError,
    PathProfile,
    default_documents_root,
    get_path_profile,
    offline_base_dir,
    resolve_offline_root,
    set_path_profile,
    validate_profile,
)

# --------------------------------------------------------------------------
# pure chain (resolve_offline_root)
# --------------------------------------------------------------------------


def test_env_wins_over_everything():
    got = resolve_offline_root("/env/base", "/profile/root", "/default/root", "synop")
    assert got.parts[-2:] == ("env", "base")[:0] or True  # shape check below
    assert str(got).endswith("synop")
    assert got == Path("/env/base/synop")


def test_empty_env_ignored_profile_wins():
    assert resolve_offline_root("", "/profile/root", "/default/root", "synop") == (
        Path("/profile/root/synop")
    )


def test_empty_profile_falls_to_default():
    assert resolve_offline_root(None, "", "/default/root", "synop") == (
        Path("/default/root/synop")
    )


def test_default_when_nothing_configured():
    assert resolve_offline_root(None, None, "/default/root", "synop") == (
        Path("/default/root/synop")
    )


# --------------------------------------------------------------------------
# validate_profile (mirror of the Rust rules and messages)
# --------------------------------------------------------------------------


def test_validate_accepts_offline_only():
    validate_profile(PathProfile(offline_root="/data/arca"))


def test_validate_accepts_windows_absolute():
    validate_profile(PathProfile(offline_root="C:\\data\\arca"))
    validate_profile(PathProfile(offline_root="D:/data"))


def test_validate_rejects_relative_offline_root():
    with pytest.raises(PathConfigError) as exc:
        validate_profile(PathProfile(offline_root="data/arca"))
    assert str(exc.value) == "offline_root debe ser una ruta absoluta (se recibió 'data/arca')"


def test_validate_rejects_empty_online_root():
    with pytest.raises(PathConfigError) as exc:
        validate_profile(PathProfile(offline_root="/a", online_root=""))
    assert str(exc.value) == "online_root, si se define, no puede ser vacío"


def test_validate_rejects_relative_online_root():
    with pytest.raises(PathConfigError) as exc:
        validate_profile(PathProfile(offline_root="/a", online_root="x"))
    assert str(exc.value) == "online_root debe ser una ruta absoluta (se recibió 'x')"


def test_validate_rejects_online_equals_offline():
    # Rust normalizar lowercases only the FIRST byte, so equality here means
    # the same string modulo trailing slashes and the leading drive letter.
    with pytest.raises(PathConfigError) as exc:
        validate_profile(PathProfile(offline_root="/a/", online_root="/a"))
    assert "no pueden apuntar a la misma carpeta" in str(exc.value)
    # Different roots never conflict.
    validate_profile(PathProfile(offline_root="/a/", online_root="/B"))


def test_validate_rejects_relative_summaries_dir():
    with pytest.raises(PathConfigError) as exc:
        validate_profile(PathProfile(offline_root="/a", summaries_dir="x"))
    assert str(exc.value) == "summaries_dir debe ser una ruta absoluta (se recibió 'x')"


def test_validate_rejects_summaries_equals_offline():
    with pytest.raises(PathConfigError) as exc:
        validate_profile(PathProfile(offline_root="/a", summaries_dir="/a"))
    assert "no puede coincidir con offline_root" in str(exc.value)


# --------------------------------------------------------------------------
# PathProfile persistence (app_config KV, key 'path_config')
# --------------------------------------------------------------------------


def test_path_profile_roundtrip(tmp_path):
    conn = sqlite3.connect(tmp_path / "p.db")
    conn.execute(
        "CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    assert get_path_profile(conn) is None
    profile = PathProfile(
        offline_root="/data/arca",
        online_root="/drive/arca",
        backups_max_age_days=30,
        summaries_dir="/data/summaries",
    )
    set_path_profile(conn, profile)
    assert get_path_profile(conn) == profile


def test_path_profile_corrupt_json_is_loud(tmp_path):
    """P1.4 lesson: a corrupt profile never silently falls back to the default."""
    conn = sqlite3.connect(tmp_path / "p.db")
    conn.execute(
        "CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO app_config (key, value) VALUES (?, ?)", (PATH_CONFIG_KEY, "{corrupto")
    )
    with pytest.raises(PathConfigError) as exc:
        get_path_profile(conn)
    assert "path_config corrupto" in str(exc.value)


def test_set_path_profile_rejects_invalid(tmp_path):
    conn = sqlite3.connect(tmp_path / "p.db")
    conn.execute(
        "CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    with pytest.raises(PathConfigError):
        set_path_profile(conn, PathProfile(offline_root="relativa"))
    assert conn.execute("SELECT COUNT(*) FROM app_config").fetchone()[0] == 0


# --------------------------------------------------------------------------
# full chain with monkeypatched env
# --------------------------------------------------------------------------


def _db_with_profile(tmp_path, profile: PathProfile | None):
    conn = sqlite3.connect(tmp_path / "chain.db")
    conn.execute(
        "CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    if profile is not None:
        conn.execute(
            "INSERT INTO app_config (key, value) VALUES (?, ?)",
            (PATH_CONFIG_KEY, json.dumps(profile.to_dict())),
        )
    return conn


def test_chain_env_beats_profile(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_BASE_DIR, "/env/base")
    conn = _db_with_profile(tmp_path, PathProfile(offline_root="/profile/root"))
    got = offline_base_dir(conn, default_root="/default/root")
    assert got == Path("/env/base/synop")


def test_chain_profile_beats_default(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_BASE_DIR, raising=False)
    conn = _db_with_profile(tmp_path, PathProfile(offline_root="/profile/root"))
    got = offline_base_dir(conn, default_root="/default/root")
    assert got == Path("/profile/root/synop")


def test_chain_default_when_no_env_no_profile(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_BASE_DIR, raising=False)
    conn = _db_with_profile(tmp_path, None)
    got = offline_base_dir(conn, default_root="/default/root")
    assert got == Path("/default/root/synop")


def test_chain_empty_env_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_BASE_DIR, "")
    conn = _db_with_profile(tmp_path, PathProfile(offline_root="/profile/root"))
    got = offline_base_dir(conn, default_root="/default/root")
    assert got == Path("/profile/root/synop")


def test_chain_corrupt_profile_is_loud(monkeypatch, tmp_path):
    """Corrupt PathProfile + no env override must raise, not fall to default."""
    monkeypatch.delenv(ENV_BASE_DIR, raising=False)
    conn = _db_with_profile(tmp_path, None)
    conn.execute(
        "INSERT INTO app_config (key, value) VALUES (?, ?)", (PATH_CONFIG_KEY, "{broken")
    )
    with pytest.raises(PathConfigError):
        offline_base_dir(conn, default_root="/default/root")


def test_default_documents_root_is_documents_arca(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_documents_root() == tmp_path / "Documents" / "ARCA"


def test_env_base_dir_constant():
    assert ENV_BASE_DIR == "ARCA_BASE_DIR"
