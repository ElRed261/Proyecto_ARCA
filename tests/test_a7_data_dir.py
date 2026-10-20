"""A7 — the database lives in the per-user data directory of each OS.

`platformdirs` decides the location (option A), `OMS_DATA_DIR` overrides it,
and the platform is injectable so every branch is covered from one host:
Windows uses `%LOCALAPPDATA%`, macOS `~/Library/Application Support` and Linux
`$XDG_DATA_HOME`.
"""


from oms_core import paths as paths_mod


def test_the_override_wins_over_every_platform(tmp_path):
    env = {"OMS_DATA_DIR": str(tmp_path / "elegido")}
    assert paths_mod.data_dir(env) == tmp_path / "elegido"
    assert paths_mod.data_dir(env, platform="win32") == tmp_path / "elegido"
    assert paths_mod.data_dir(env, platform="darwin") == tmp_path / "elegido"


def test_linux_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert paths_mod.data_dir({}, platform="linux") == tmp_path / "xdg" / "oms"


def test_windows_uses_local_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("WIN_PD_OVERRIDE_LOCAL_APPDATA", r"C:\Users\tester\AppData\Local")
    got = str(paths_mod.data_dir({}, platform="win32"))
    assert got.startswith(r"C:\Users\tester\AppData\Local")
    assert got.endswith("oms")
    assert "AppData" in got


def test_macos_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths_mod.data_dir({}, platform="darwin") == (
        tmp_path / "Library" / "Application Support" / "oms"
    )


def test_the_database_sits_inside_the_data_directory(tmp_path):
    env = {"OMS_DATA_DIR": str(tmp_path / "datos")}
    assert paths_mod.database_path(env) == tmp_path / "datos" / "oms.db"


def test_the_database_is_not_in_documents(tmp_path):
    """A synced folder breaks SQLite locking, so it must never be here."""
    env = {"OMS_DATA_DIR": str(tmp_path / "datos")}
    documents = paths_mod.default_documents_root({"HOME": str(tmp_path)})
    assert documents not in paths_mod.database_path(env).parents
    assert paths_mod.database_path(env).parent != documents


# ------------------------------------------------- Documents on Windows


def test_windows_documents_prefers_onedrive(monkeypatch, tmp_path):
    (tmp_path / "OneDrive" / "Documents").mkdir(parents=True)
    (tmp_path / "perfil" / "Documents").mkdir(parents=True)
    env = {"OneDrive": str(tmp_path / "OneDrive"),
           "USERPROFILE": str(tmp_path / "perfil")}
    got = paths_mod._documents_dir(str(tmp_path), env, platform="win32")
    assert got == tmp_path / "OneDrive" / "Documents"


def test_windows_documents_falls_back_to_the_profile(monkeypatch, tmp_path):
    (tmp_path / "perfil" / "Documents").mkdir(parents=True)
    env = {"USERPROFILE": str(tmp_path / "perfil")}
    got = paths_mod._documents_dir(str(tmp_path), env, platform="win32")
    assert got == tmp_path / "perfil" / "Documents"


def test_windows_documents_falls_back_to_home(tmp_path):
    got = paths_mod._documents_dir(str(tmp_path), {}, platform="win32")
    assert got == tmp_path / "Documents"
