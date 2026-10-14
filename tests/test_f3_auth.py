"""F3 — auth service tests, mirroring OLD .../tests/auth_flow.rs + modules/auth/mod.rs.

Covers: login success/failure, timing equalization on unknown email (via
monkeypatched verify call count, NOT wall time), 8h session expiry with an
injected clock, sweep, logout, require_role, role normalization and
seed_admin idempotency.
"""


import pytest

from oms_core.db.connection import connect
from oms_core.db.migrations import migrate
from oms_core.db.repositories import users as users_repo
from oms_core.services import auth
from oms_core.services.auth import AuthError, Session, SessionStore

PASSWORD = "Clave123!"


def make_db(tmp_path):
    conn = connect(tmp_path / "auth.db")
    migrate(conn)
    return conn


def add_user(conn, email, password=PASSWORD, role="admin", is_active=True):
    users_repo.add_user(conn, email, auth.hash_password(password), role, is_active=is_active)
    return email


def login_ok(conn, store, email, password=PASSWORD):
    return auth.login(conn, store, email, password)


# ---------------------------------------------------------------- login


def test_login_exitoso_devuelve_token_y_sesion_valida(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()
    email = add_user(conn, "flujo_login@arca.test", role="admin")

    result = login_ok(conn, store, email)
    assert result.token_type == "bearer"
    assert result.user_email == email

    session = store.validate_session(result.access_token)
    assert session.email == email
    assert session.role == "admin"


def test_login_fallido_con_password_incorrecta(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()
    email = add_user(conn, "flujo_login_bad@arca.test", role="observador")

    with pytest.raises(AuthError) as excinfo:
        auth.login(conn, store, email, "Clave-incorrecta")
    assert "Usuario o contraseña incorrectos" in str(excinfo.value)


def test_login_email_desconocido_mismo_mensaje(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()

    with pytest.raises(AuthError) as excinfo:
        auth.login(conn, store, "nadie@arca.test", "lo-que-sea")
    assert "Usuario o contraseña incorrectos" in str(excinfo.value)


def test_usuario_inactivo_no_puede_loguear(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()
    email = add_user(conn, "inactivo@arca.test", role="observador", is_active=False)

    with pytest.raises(AuthError) as excinfo:
        auth.login(conn, store, email, PASSWORD)
    assert "desactivada" in str(excinfo.value)


def test_timing_equalization_email_desconocido_verifica_hash_dummy(tmp_path, monkeypatch):
    """Unknown email must still run ONE bcrypt verify (against the dummy hash)
    so the response timing cannot enumerate users — oracle login_user_logic."""
    conn = make_db(tmp_path)
    store = SessionStore()

    calls = []
    real_verify = auth.verify

    def spy(password, password_hash):
        calls.append(password_hash)
        return real_verify(password, password_hash)

    monkeypatch.setattr(auth, "verify", spy)

    with pytest.raises(AuthError):
        auth.login(conn, store, "fantasma@arca.test", "Clave123!")

    assert len(calls) == 1, "unknown email must perform exactly one verify"
    assert calls[0] == auth.dummy_password_hash()


def test_email_conocido_password_mala_verifica_hash_del_usuario(tmp_path, monkeypatch):
    conn = make_db(tmp_path)
    store = SessionStore()
    email = add_user(conn, "timing_ok@arca.test", role="admin")
    stored_hash = users_repo.get_user_by_email(conn, email).password_hash

    calls = []
    real_verify = auth.verify

    def spy(password, password_hash):
        calls.append(password_hash)
        return real_verify(password, password_hash)

    monkeypatch.setattr(auth, "verify", spy)

    with pytest.raises(AuthError):
        auth.login(conn, store, email, "mala-clave")

    assert len(calls) == 1
    assert calls[0] == stored_hash


# ---------------------------------------------------------------- sessions


def test_tokens_de_sesion_son_csprng_unicos(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()
    u1 = add_user(conn, "tokens_a@arca.test")
    u2 = add_user(conn, "tokens_b@arca.test")

    t1 = login_ok(conn, store, u1).access_token
    t2 = login_ok(conn, store, u2).access_token

    for token in (t1, t2):
        assert len(token) == 64, "token must be hex of 32 bytes"
        assert all(c in "0123456789abcdef" for c in token)
    assert t1 != t2


def test_validate_session_rechaza_token_fuera_de_sesion():
    store = SessionStore()
    with pytest.raises(AuthError) as excinfo:
        store.validate_session("token-que-no-existe")
    assert "Sesión no encontrada" in str(excinfo.value)


def test_sesion_expirada_tras_8_horas_con_reloj_inyectado():
    now = 1_000_000
    store = SessionStore(clock=lambda: now)
    token = store.create_session(1, "x@arca.test", "admin")

    now += auth.SESSION_TTL_SECS  # exactly 8h: still valid (oracle uses >)
    assert store.validate_session(token).email == "x@arca.test"

    now += 1  # one second past TTL: expired
    with pytest.raises(AuthError) as excinfo:
        store.validate_session(token)
    assert "expirada" in str(excinfo.value)
    # the expired entry is removed: the store must not grow unbounded (R5)
    assert store._sessions == {}


def test_sweep_expired_barra_solo_las_vencidas():
    now = 500_000
    store = SessionStore(clock=lambda: now)
    viejo = store.create_session(1, "old@arca.test", "admin")
    nuevo = store.create_session(2, "new@arca.test", "admin")
    store._sessions[viejo] = Session(
        user_id=1,
        email="old@arca.test",
        role="admin",
        created_at=now - auth.SESSION_TTL_SECS - 10,
    )

    store.sweep_expired()
    assert viejo not in store._sessions
    assert nuevo in store._sessions


def test_logout_invalida_el_token(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()
    email = add_user(conn, "logout@arca.test")
    token = login_ok(conn, store, email).access_token

    auth.logout(store, token)
    with pytest.raises(AuthError) as excinfo:
        store.validate_session(token)
    assert "Sesión no encontrada" in str(excinfo.value)


# ---------------------------------------------------------------- require_role


def test_require_role_admite_admin_y_rechaza_observador(tmp_path):
    conn = make_db(tmp_path)
    store = SessionStore()
    admin = add_user(conn, "roles_admin@arca.test", role="admin")
    observador = add_user(conn, "roles_observador@arca.test", role="observador")

    session = auth.require_role(store, login_ok(conn, store, admin).access_token, ["admin"])
    assert session.role == "admin"

    obs_token = login_ok(conn, store, observador).access_token
    with pytest.raises(PermissionError) as excinfo:
        auth.require_role(store, obs_token, ["admin"])
    assert "privilegios insuficientes" in str(excinfo.value)

    # the observer does pass with its own role
    session = auth.require_role(store, obs_token, ["observador"])
    assert session.role == "observador"


def test_require_role_rechaza_token_invalido():
    store = SessionStore()
    with pytest.raises(AuthError):
        auth.require_role(store, "no-existe", ["admin"])


# ---------------------------------------------------------------- roles


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ADMIN", "admin"),
        ("Administrador", "admin"),
        ("administrador", "admin"),
        ("Control_Calidad", "control_calidad"),
        ("encargado", "encargado"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalize_role(raw, expected):
    assert auth.normalize_role(raw) == expected


def test_require_role_acepta_alias_administrador(tmp_path):
    """'administrador' is an alias of 'admin' (frontend auth.js)."""
    conn = make_db(tmp_path)
    store = SessionStore()
    email = add_user(conn, "alias@arca.test", role="administrador")
    token = login_ok(conn, store, email).access_token

    session = auth.require_role(store, token, ["admin"])
    assert session.role == "administrador"


# ---------------------------------------------------------------- seed


def test_seed_admin_crea_cuatro_usuarios_y_archivo_primer_inicio(tmp_path):
    conn = make_db(tmp_path)
    creds = auth.seed_admin(conn, tmp_path)

    assert creds is not None
    assert set(creds) == {
        "admin@arca.rd",
        "encargado@arca.rd",
        "observador@arca.rd",
        "calidad@arca.rd",
    }
    for email, password in creds.items():
        assert len(password) == 12
        user = users_repo.get_user_by_email(conn, email)
        assert user is not None and user.is_active

    marker = tmp_path / "primer_inicio.txt"
    assert marker.exists()
    content = marker.read_text(encoding="utf-8")
    for email, password in creds.items():
        assert f"{email} : {password}" in content
    assert "IMPORTANTE" in content

    # seeded credentials actually log in
    store = SessionStore()
    result = auth.login(conn, store, "admin@arca.rd", creds["admin@arca.rd"])
    assert store.validate_session(result.access_token).role == "admin"


def test_seed_admin_es_idempotente(tmp_path):
    conn = make_db(tmp_path)
    first = auth.seed_admin(conn, tmp_path)
    marker = tmp_path / "primer_inicio.txt"
    first_mtime = marker.stat().st_mtime_ns

    assert auth.seed_admin(conn, tmp_path) is None
    assert users_repo.count_users(conn) == 4
    assert marker.stat().st_mtime_ns == first_mtime, "marker must not be rewritten"

    # the first-run passwords keep working after a re-run
    store = SessionStore()
    result = auth.login(conn, store, "admin@arca.rd", first["admin@arca.rd"])
    assert result.user_email == "admin@arca.rd"


def test_seed_admin_con_usuarios_preexistentes_no_hace_nada(tmp_path):
    conn = make_db(tmp_path)
    add_user(conn, "ya_habia@arca.test", role="admin")

    assert auth.seed_admin(conn, tmp_path) is None
    assert not (tmp_path / "primer_inicio.txt").exists()
    assert users_repo.count_users(conn) == 1
