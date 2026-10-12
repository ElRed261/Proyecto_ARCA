mod helpers;

use app_lib::infrastructure::storage::paths_config::{
    get_path_config_db, set_path_config_checked, validate_profile, PathProfile,
};
use helpers::{create_test_pool, TestUser};

fn absolute_dir(tag: &str) -> String {
    let base = std::env::temp_dir().join(format!("arca_paths_{tag}"));
    std::fs::create_dir_all(&base).expect("debe poder crear el temp dir de prueba");
    base.to_string_lossy().to_string()
}

#[test]
fn set_then_get_path_config_roundtrip() {
    let pool = create_test_pool();
    let adm = TestUser::create(&pool, "paths_roundtrip@arca.test", "Clave123!", "admin");
    let conn = pool.get().expect("pool debe entregar conexión");

    let profile = PathProfile {
        offline_root: absolute_dir("offline_roundtrip"),
        online_root: Some(absolute_dir("online_roundtrip")),
        backups_max_age_days: Some(30),
        summaries_dir: None,
    };

    set_path_config_checked(
        &adm.session_store,
        &adm.login.access_token,
        &conn,
        &profile,
    )
    .expect("admin debe poder guardar un PathProfile válido");

    let got = get_path_config_db(&conn)
        .expect("lectura no debe fallar")
        .expect("debe existir configuración tras el set");

    assert_eq!(got, profile, "el roundtrip debe conservar el perfil exacto");
}

#[test]
fn get_sin_config_devuelve_none() {
    let pool = create_test_pool();
    let conn = pool.get().expect("pool debe entregar conexión");

    let got = get_path_config_db(&conn).expect("lectura no debe fallar");
    assert!(
        got.is_none(),
        "sin configuración previa debe devolver None, obtuvo {:?}",
        got
    );
}

#[test]
fn set_path_config_rechaza_no_admin() {
    let pool = create_test_pool();
    let obs = TestUser::create(&pool, "paths_obs@arca.test", "Clave123!", "observador");
    let adm = TestUser::create(&pool, "paths_adm@arca.test", "Clave123!", "admin");
    let conn = pool.get().expect("pool debe entregar conexión");

    let profile = PathProfile {
        offline_root: absolute_dir("offline_roles"),
        online_root: None,
        backups_max_age_days: None,
        summaries_dir: None,
    };

    let err = set_path_config_checked(
        &obs.session_store,
        &obs.login.access_token,
        &conn,
        &profile,
    )
    .expect_err("un observador no debe poder configurar rutas");
    assert!(
        err.contains("privilegios insuficientes"),
        "el error debe indicar falta de privilegios, fue: {}",
        err
    );

    set_path_config_checked(
        &adm.session_store,
        &adm.login.access_token,
        &conn,
        &profile,
    )
    .expect("el admin sí debe poder configurar rutas");
}

#[test]
fn set_path_config_rechaza_token_invalido() {
    let pool = create_test_pool();
    let adm = TestUser::create(&pool, "paths_token@arca.test", "Clave123!", "admin");
    let conn = pool.get().expect("pool debe entregar conexión");

    let profile = PathProfile::default_offline_only(&absolute_dir("offline_token"));

    let err = set_path_config_checked(&adm.session_store, "token-inexistente", &conn, &profile)
        .expect_err("un token inexistente no debe configurar rutas");
    assert!(
        err.contains("Sesión no encontrada"),
        "el error debe indicar sesión inválida, fue: {}",
        err
    );
}

#[test]
fn validate_profile_rejects_same_offline_and_online() {
    let same = absolute_dir("mismos");
    let profile = PathProfile {
        offline_root: same.clone(),
        online_root: Some(same),
        backups_max_age_days: None,
        summaries_dir: None,
    };

    let err = validate_profile(&profile)
        .expect_err("online_root igual a offline_root debe ser rechazado");
    assert!(
        err.contains("online") && err.contains("offline"),
        "el error debe explicar el conflicto online/offline, fue: {}",
        err
    );
}

#[test]
fn validate_profile_rejecta_ruta_relativa() {
    let profile = PathProfile {
        offline_root: "ruta/relativa/arca".to_string(),
        online_root: None,
        backups_max_age_days: None,
        summaries_dir: None,
    };

    let err = validate_profile(&profile)
        .expect_err("una ruta relativa no debe aceptarse");
    assert!(
        err.contains("relativa") || err.contains("absoluta"),
        "el error debe explicar que se requiere ruta absoluta, fue: {}",
        err
    );
}
