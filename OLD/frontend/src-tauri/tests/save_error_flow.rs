mod helpers;

use app_lib::json_handler::synoptic::save_observation_json_core;
use serde_json::Value;

fn parse_error(err: &str) -> Value {
    serde_json::from_str(err)
        .expect("los errores de guardado deben ser JSON parseable: {stage, path, detail}")
}

fn obs() -> serde_json::Value {
    serde_json::json!({"00Z": {"ts": "30.0"}})
}

#[test]
fn save_fecha_invalida_reporta_stage_validate() {
    let dir = helpers::with_arca_dir_returning(|base| base.to_path_buf());
    let err = save_observation_json_core(
        &dir.join("synop"),
        "78451".to_string(),
        "fecha-rota".to_string(),
        obs(),
        None,
        None,
        None,
        None,
        |_| None,
    )
    .expect_err("fecha rota debe fallar");

    let e = parse_error(&err);
    assert_eq!(e.get("stage").and_then(|v| v.as_str()), Some("validate"));
    assert!(
        e.get("detail").and_then(|v| v.as_str()).is_some(),
        "debe incluir detail: {}",
        err
    );
}

#[test]
fn save_dir_imposible_reporta_stage_dirs_y_path() {
    // /dev/null es un archivo: create_dir_all bajo ese padre falla
    let err = save_observation_json_core(
        std::path::Path::new("/dev/null/not-a-dir"),
        "78451".to_string(),
        helpers::FECHA_OK.to_string(),
        obs(),
        None,
        None,
        None,
        None,
        |_| None,
    )
    .expect_err("crear dirs bajo un archivo debe fallar");

    let e = parse_error(&err);
    assert_eq!(e.get("stage").and_then(|v| v.as_str()), Some("dirs"));
    let path = e
        .get("path")
        .and_then(|v| v.as_str())
        .expect("stage dirs debe incluir path");
    assert!(
        path.contains("78451") || path.contains("2026") || path.contains("08"),
        "el path debe referirse al destino de la estación: {}",
        path
    );
}

#[test]
fn save_json_corrupto_reporta_stage_read() {
    // pre-crear un archivo corrupto: la segunda escritura debe fallar leyendo
    let (base, archivo) = helpers::with_obs_target_corrupt(helpers::FECHA_OK);
    // el archivo corrupto existe → merge_json_file debe leer y fallar
    let err = save_observation_json_core(
        &base.join("synop"),
        "78451".to_string(),
        helpers::FECHA_OK.to_string(),
        obs(),
        None,
        None,
        None,
        None,
        |_| None,
    )
    .expect_err("leer un JSON corrupto durante el merge debe fallar");

    let e = parse_error(&err);
    assert_eq!(e.get("stage").and_then(|v| v.as_str()), Some("read"));
    let path = e
        .get("path")
        .and_then(|v| v.as_str())
        .expect("stage read debe llevar el path del archivo");
    assert!(
        path.ends_with(archivo.file_name().unwrap().to_string_lossy().to_string().as_str()),
        "el path debe señalar el archivo objetivo, fue: {}",
        path
    );
}
