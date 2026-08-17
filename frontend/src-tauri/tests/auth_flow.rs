mod helpers;

use app_lib::auth;
use app_lib::ports::UserRepository;
use helpers::{create_test_pool, create_user_and_login, TestUser};

#[test]
fn login_exitoso_devuelve_token_y_session_valida() {
    let pool = create_test_pool();
    let user = create_user_and_login(&pool);

    let session = user
        .session_store
        .validate_session(&user.login.access_token)
        .expect("el token recién emitido debe ser válido");
    assert_eq!(session.email, user.email, "el session debe corresponder al email logueado");
    assert_eq!(session.role, "admin", "el session debe conservar el rol del usuario");
}

#[test]
fn login_fallido_con_password_incorrecta() {
    let pool = create_test_pool();
    let user = TestUser::create(&pool, "flujo_login_bad@arca.test", "Clave123!", "observador");

    let err = auth::login_user_logic(&user.repo, &user.session_store, &user.email, "Clave-incorrecta")
        .expect_err("password incorrecta debe fallar el login");
    assert!(err.contains("Usuario o contraseña incorrectos"), "error inesperado: {}", err);
}

#[test]
fn validate_session_rechaza_token_fuera_de_sesion() {
    let pool = create_test_pool();
    let user = TestUser::create(&pool, "token_invalido@arca.test", "Clave123!", "admin");

    let err = user.session_store.validate_session("token-que-no-existe").unwrap_err();
    assert!(
        err.to_string().contains("Sesión no encontrada"),
        "error inesperado: {}",
        err
    );
}

#[test]
fn logout_invalida_el_token() {
    let pool = create_test_pool();
    let user = TestUser::create(&pool, "logout@arca.test", "Clave123!", "admin");

    user.session_store.delete_session(&user.login.access_token);

    let err = user.session_store.validate_session(&user.login.access_token).unwrap_err();
    assert!(
        err.to_string().contains("Sesión no encontrada"),
        "el token debe quedar inválido tras logout"
    );
}

#[test]
fn change_password_permite_login_con_nueva_password_y_bloquea_la_vieja() {
    let pool = create_test_pool();
    let user = TestUser::create(&pool, "cambio_password@arca.test", "Clave123!", "admin");
    let nueva_password = "NuevaClave456!";

    let user_id = get_user_id(&user, &user.email);

    auth::change_password_logic(&user.repo, &user.session_store, &user.login.access_token, user_id, nueva_password)
        .expect("el usuario debe poder cambiar su propia contraseña");

    let err = auth::login_user_logic(&user.repo, &user.session_store, &user.email, &user.password)
        .expect_err("la password vieja no debe seguir funcionando");
    assert!(err.contains("Usuario o contraseña incorrectos"), "error inesperado: {}", err);

    let nuevo_login = auth::login_user_logic(&user.repo, &user.session_store, &user.email, nueva_password)
        .expect("el login con la nueva password debe funcionar");
    assert_eq!(nuevo_login.user_email, user.email, "debe loguear al mismo usuario");
}

#[test]
fn require_role_admite_admin_y_rechaza_observador() {
    let pool = create_test_pool();
    let admin = TestUser::create(&pool, "roles_admin@arca.test", "Clave123!", "admin");
    let observador = TestUser::create(&pool, "roles_observador@arca.test", "Clave123!", "observador");

    let session = auth::require_role(&admin.session_store, &admin.login.access_token, &["admin"])
        .expect("admin debe pasar require_role con rol admin");
    assert_eq!(session.role, "admin", "debe devolver la sesión del admin");

    let err = auth::require_role(&observador.session_store, &observador.login.access_token, &["admin"])
        .map(|_| ())
        .unwrap_err();
    assert!(
        err.to_string().contains("privilegios insuficientes"),
        "un observador con require_role(admin) debe fallar, error inesperado: {}",
        err
    );

    let session = auth::require_role(&observador.session_store, &observador.login.access_token, &["observador"])
        .expect("el observador sí debe pasar require_role con su propio rol");
    assert_eq!(session.role, "observador", "debe devolver la sesión del observador");
}

#[test]
fn usuario_inactivo_no_puede_loguear() {
    let pool = create_test_pool();
    let user = TestUser::create(&pool, "inactivo@arca.test", "Clave123!", "observador");
    let user_id = get_user_id(&user, &user.email);

    user.repo
        .update(user_id, "observador", false)
        .expect("debe poder desactivar el usuario");

    let err = auth::login_user_logic(&user.repo, &user.session_store, &user.email, &user.password)
        .expect_err("un usuario desactivado no debe loguear");
    assert!(
        err.contains("desactivada"),
        "debe indicar que la cuenta está desactivada, error inesperado: {}",
        err
    );
}

fn get_user_id(user: &TestUser, email: &str) -> i64 {
    user.repo
        .find_by_email(email)
        .expect("debe acompletar la búsqueda sin error")
        .map(|u| u.id)
        .unwrap_or_else(|| panic!("usuario {} no encontrado", email))
}