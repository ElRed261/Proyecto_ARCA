mod helpers;

use app_lib::json_handler::synoptic::{get_observation_core, save_observation_json_core};
use helpers::with_arca_dir;
use serde_json::{json, Value};

const FECHA: &str = "2026-08-15";

fn obs_1_hora() -> Value {
    json!({
        "00Z": {
            "ts": "30.0",
            "th": "20.0",
            "pres_est": "1016.0",
            "p3": "1012.0",
            "p24": "1010.0",
            "pres_nmm": "1016.5",
            "punto_rocio": "15.0",
            "meteo_2_1": "12023",
            "meteo_4_irixhvv": "001",
            "meteo_4_1": "31018",
            "meteo_4_6": "02//",
        }
    })
}

#[allow(clippy::too_many_arguments)]
fn guardar(base: &std::path::Path, code: &str, obs: Value) {
    // `base` ya apunta a {temp}/synop — misma convención que observation_flow
    save_observation_json_core(
        base,
        code.to_string(),
        FECHA.to_string(),
        obs,
        None,
        None,
        None,
        None,
        |_| None,
    )
    .expect("el guardado con capitalización mixta debe funcionar");
}

#[test]
fn guardar_normaliza_el_codigo_a_minusculas() {
    with_arca_dir(|base| {
        let synop = base.join("synop");
        guardar(&synop, "MiEstacion", obs_1_hora());

        // El archivo físico vive en minúsculas
        let esperado = synop
            .join("miestacion")
            .join("2026")
            .join("08")
            .join("miestacion15082026.json");
        assert!(
            esperado.exists(),
            "el archivo debe existir con código normalizado en {:?}",
            esperado
        );

        // Y NO debe existir una carpeta con mayúsculas (danger en FS case-insensitive)
        assert!(
            !synop.join("MiEstacion").exists(),
            "no debe crearse carpeta con mayúsculas: en Windows/macOS chocaría con la minúscula"
        );
    });
}

#[test]
fn lectura_con_otro_case_lee_el_mismo_archivo() {
    with_arca_dir(|base| {
        let synop = base.join("synop");
        guardar(&synop, "MiEstacion", obs_1_hora());

        let leido = get_observation_core(&synop, "MIESTACION".to_string(), FECHA.to_string())
            .expect("la lectura con mayúsculas debe encontrar el archivo en minúsculas");
        // contrato de lectura: estructura plana, la hora queda en la raíz
        assert!(
            leido.get("00Z").is_some(),
            "la hora 00Z debe estar presente en la respuesta plana",
        );
    });
}

#[test]
fn codigo_con_underscore_tambien_se_normaliza() {
    with_arca_dir(|base| {
        let synop = base.join("synop");
        guardar(&synop, "EstC", obs_1_hora());

        let esperado = synop
            .join("estc")
            .join("2026")
            .join("08")
            .join("estc15082026.json");
        assert!(
            esperado.exists(),
            "underscore deve normalizarse también: {:?}",
            esperado
        );
    });
}
