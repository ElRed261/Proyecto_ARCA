"""Round 15 — the default storage layout under Documents.

The owner asked for a default route that exists even though the admin can
change it, living in Documents, and sectioned efficiently inside. These
tests cover that contract: the default root, the closed section set, the
tree creation (idempotent, never destructive), and the fact that the
configured profile still wins over the default everywhere, audit included.
"""

from pathlib import Path

import pytest

from oms_core import paths as paths_mod
from oms_core.paths import (
    SECTIONS,
    PathConfigError,
    PathProfile,
    default_documents_root,
    ensure_directories,
    offline_base_dir,
    section_dir,
    set_path_profile,
)
from oms_core.services import audit as audit_service


@pytest.fixture()
def conn(fresh_db):
    return fresh_db


# ---------------------------------------------------------------- S1 default


def test_default_root_is_documents_oms(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DOCUMENTS_DIR", raising=False)
    assert default_documents_root() == tmp_path / "Documents" / "OMS"


def test_default_root_exists_after_ensure(monkeypatch, tmp_path, conn):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DOCUMENTS_DIR", raising=False)
    root = ensure_directories(conn, env={"HOME": str(tmp_path)})
    assert root == tmp_path / "Documents" / "OMS" / "synop"
    assert root.is_dir()


# ---------------------------------------------------------------- S2 sections


def test_sections_are_the_closed_set():
    assert SECTIONS == ("synop", "resumenes", "exportaciones", "respaldos")


def test_section_dir_returns_the_child():
    assert section_dir("/base", "resumenes") == Path("/base/resumenes")


def test_section_dir_rejects_an_unknown_section():
    with pytest.raises(PathConfigError):
        section_dir("/base", "no-existe")


def test_ensure_directories_creates_every_section(conn, tmp_path):
    root = ensure_directories(conn, default_root=str(tmp_path))
    for section in SECTIONS:
        assert (root / section).is_dir(), section


def test_ensure_directories_is_idempotent_and_non_destructive(conn, tmp_path):
    root = ensure_directories(conn, default_root=str(tmp_path))
    keeper = root / "exportaciones" / "ya-estaba.xlsx"
    keeper.write_text("datos", encoding="utf-8")
    again = ensure_directories(conn, default_root=str(tmp_path))
    assert again == root
    assert keeper.read_text(encoding="utf-8") == "datos"


def test_ensure_directories_can_target_one_section(conn, tmp_path):
    root = ensure_directories(conn, section="respaldos", default_root=str(tmp_path))
    assert (root / "respaldos").is_dir()
    assert not (root / "exportaciones").exists()


# ------------------------------------------------------- S3 chain unchanged


def test_env_override_still_wins_over_profile_and_default(conn, tmp_path):
    set_path_profile(conn, PathProfile(offline_root=str(tmp_path / "perfil")))
    got = ensure_directories(
        conn, env={"ARCA_BASE_DIR": str(tmp_path / "env")},
        default_root=str(tmp_path / "default"),
    )
    assert got == tmp_path / "env" / "synop"


def test_profile_still_wins_over_the_default(conn, tmp_path):
    set_path_profile(conn, PathProfile(offline_root=str(tmp_path / "perfil")))
    assert offline_base_dir(conn, env={}, default_root=str(tmp_path)) == (
        tmp_path / "perfil" / "synop"
    )


def test_configured_root_moves_the_audit_browser(conn, tmp_path):
    """S4: one source of truth — the profile reaches the audit browser."""
    set_path_profile(conn, PathProfile(offline_root=str(tmp_path / "perfil")))
    assert audit_service.resolve_base_dir(conn) == tmp_path / "perfil" / "synop"


def test_audit_browser_follows_the_default_when_unset(monkeypatch, tmp_path, conn):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv(paths_mod.ENV_BASE_DIR, raising=False)
    assert audit_service.resolve_base_dir(conn) == (
        tmp_path / "Documents" / "OMS" / "synop"
    )


def test_audit_default_base_dir_has_no_second_literal(monkeypatch, tmp_path):
    monkeypatch.setenv(paths_mod.ENV_BASE_DIR, str(tmp_path / "env"))
    assert audit_service.default_base_dir() == tmp_path / "env" / "synop"


# ------------------------------------------------- S1: localized Documents


def test_documents_dir_follows_xdg_env(tmp_path):
    env = {"HOME": str(tmp_path), "XDG_DOCUMENTS_DIR": str(tmp_path / "Doc")}
    assert paths_mod.default_documents_root(env) == tmp_path / "Doc" / "OMS"


def test_documents_dir_reads_user_dirs_with_home_expansion(tmp_path):
    config = tmp_path / ".config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text(
        '# comentario\nXDG_DOCUMENTS_DIR="$HOME/Documentos"\n', encoding="utf-8")
    env = {"HOME": str(tmp_path)}
    assert paths_mod.default_documents_root(env) == tmp_path / "Documentos" / "OMS"


def test_documents_dir_falls_back_to_english_documents(tmp_path):
    env = {"HOME": str(tmp_path)}
    assert paths_mod.default_documents_root(env) == tmp_path / "Documents" / "OMS"


def test_ensure_directories_uses_the_localized_documents_dir(tmp_path, conn):
    config = tmp_path / ".config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text(
        'XDG_DOCUMENTS_DIR="$HOME/Documentos"\n', encoding="utf-8")
    root = ensure_directories(conn, env={"HOME": str(tmp_path)})
    assert root == tmp_path / "Documentos" / "OMS" / "synop"
    assert (root / "resumenes").is_dir()
