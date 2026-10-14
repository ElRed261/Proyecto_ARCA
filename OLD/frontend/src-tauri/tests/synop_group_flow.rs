mod helpers;

use app_lib::json_handler::synoptic::save_observation_json_core;
use serde_json::{json, Value};

fn guardar(base: &std::path::Path, horas: Value) -> Result<(), String> {
    save_observation_json_core(
        &base.join("synop"),
        "78451".to_string(),
        "2026-08-15".to_string(),
        horas,
        None,
        None,
        None,
        None,
        |_| None,
    )
    .map(|_| ())
}

/// grupos conformes (5 chars, dígitos y "/") guardan sin error
#[test]
fn grupos_validos_guardan_ok() {
    helpers::with_arca_dir(|base| {
        let obs = json!({
            "00Z": {
                "ts": "30.0",
                "meteo_4_irixhvv": "32466",
                "meteo_2_1": "12023",
                "meteo_4_1": "31018",
                "meteo_4_6": "120//",
                "extra_8ns_1": "32///"
            }
        });
        guardar(base, obs).expect("grupos de 5 con dígitos y / deben guardar");
    });
}

/// más de 5 caracteres → rechazo con stage validate señalando el campo
#[test]
fn grupo_de_mas_de_5_caracteres_rechaza() {
    helpers::with_arca_dir(|base| {
        let obs = json!({
            "00Z": {
                "ts": "30.0",
                "meteo_4_irixhvv": "324661"
            }
        });

        let err = guardar(base, obs).expect_err("IrIxHVV de 6 dígitos debe fallar");
        let parsed: Value = serde_json::from_str(&err)
            .expect("los errores de guardar deben ser SaveErr JSON");
        assert_eq!(parsed["stage"], "validate", "fue: {}", err);
        assert!(
            parsed["detail"]
                .as_str()
                .map(|d| d.contains("meteo_4_irixhvv"))
                .unwrap_or(false),
            "el detalle debe señalar el campo, fue: {}",
            err
        );
    });
}

/// letras o símbolos en el grupo → rechazo
#[test]
fn grupo_con_caracteres_invalidos_rechaza() {
    helpers::with_arca_dir(|base| {
        let obs = json!({
            "00Z": {
                "meteo_4_6": "12a5/"
            }
        });

        let err = guardar(base, obs).expect_err("letras no son válidas en un grupo");
        let parsed: Value = serde_json::from_str(&err).expect("debe ser SaveErr JSON");
        assert_eq!(parsed["stage"], "validate");
    });
}

/// ausencia total: "/////" permitido
#[test]
fn grupo_todo_barras_permitido() {
    helpers::with_arca_dir(|base| {
        let obs = json!({
            "00Z": {
                "meteo_4_irixhvv": "/////",
                "meteo_2_1": "/////"
            }
        });
        guardar(base, obs).expect("///// es ausencia total válida");
    });
}
