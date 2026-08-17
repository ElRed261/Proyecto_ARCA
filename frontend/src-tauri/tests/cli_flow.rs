mod helpers;

use app_lib::json_handler::cli::{load_cli3074_json_core, load_cli4074_json_core, load_cli5074_json_core};
use helpers::with_arca_dir;
use serde_json::{json, Value};
use std::path::Path;

const STATION: &str = "78451";
const FECHA: &str = "2026-08-15";

fn cli_filepath(base: &Path) -> std::path::PathBuf {
    base.join(STATION).join("2026").join("08").join("7845115082026.json")
}

fn write_cli_file(base: &Path, cli_key: &str, data: Value) {
    let root = json!({
        "meta": {"estacion": STATION, "fecha": "15082026"},
        cli_key: data,
    });
    let path = cli_filepath(base);
    std::fs::create_dir_all(path.parent().expect("directorio padre del archivo CLI"))
        .expect("crear dirs del layout ARCA");
    std::fs::write(path, serde_json::to_string_pretty(&root).expect("serializar CLI"))
        .expect("escribir archivo CLI");
}

#[test]
fn load_cli3074_core_carga_y_calcula_campos_automaticos() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        write_cli_file(
            &synop_base,
            "cli3074",
            json!({
                "horas": {
                    "1": {
                        "pres_est": "1013.5",
                        "p3": "1010.0",
                        "meteo_4_irixhvv": "001",
                        "meteo_4_6": "02//",
                        "meteo_4_1": "31018",
                    }
                }
            }),
        );

        let loaded = load_cli3074_json_core(&synop_base, STATION, FECHA)
            .expect("cargar CLI 3074 no debe fallar");
        let horas = loaded.get("horas").and_then(|h| h.as_object()).expect("cli3074 con horas");
        let hora_1 = horas.get("1").and_then(|h| h.as_object()).expect("hora 1 del cli3074");

        assert_eq!(hora_1.get("tend_dif").and_then(|v| v.as_str()), Some("03.5"), "dif calculada 1013.5 - 1010.0");
        assert_eq!(hora_1.get("tend_car").and_then(|v| v.as_str()), Some("3"), "car calculada para dif > 2");
        assert_eq!(hora_1.get("visibilidad").and_then(|v| v.as_str()), Some("001"), "visibilidad desde IrIXHVV");
    });
}

#[test]
fn load_cli4074_core_devuelve_datos_de_temperatura_y_nubosidad() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        write_cli_file(
            &synop_base,
            "cli4074",
            json!({
                "2": {"temp_max": "30.0", "temp_min": "20.0"},
                "8": {"temp_max": "31.5", "temp_min": "21.0"},
            }),
        );

        let loaded = load_cli4074_json_core(&synop_base, STATION, FECHA)
            .expect("cargar CLI 4074 no debe fallar");
        assert!(
            loaded.get("2").and_then(|r| r.get("temp_max")).and_then(|v| v.as_str()) == Some("30.0"),
            "la fila 2 debe traer temp_max 30.0"
        );
        assert!(
            loaded.get("8").and_then(|r| r.get("temp_min")).and_then(|v| v.as_str()) == Some("21.0"),
            "la fila 8 debe traer temp_min 21.0"
        );
    });
}

#[test]
fn load_cli5074_core_devuelve_fenomenos_extremos() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        write_cli_file(
            &synop_base,
            "cli5074",
            json!({
                "fenomenos": ["tormenta", "neblina"],
                "notas": "sin eventos"
            }),
        );

        let loaded = load_cli5074_json_core(&synop_base, STATION, FECHA)
            .expect("cargar CLI 5074 no debe fallar");
        assert!(
            loaded.get("fenomenos").is_some(),
            "debe devolver los fenómenos registrados"
        );
        assert_eq!(
            loaded.get("notas").and_then(|v| v.as_str()),
            Some("sin eventos"),
            "las notas deben viajar intactas"
        );
    });
}

#[test]
fn load_cli_core_devuelve_null_si_no_hay_archivo() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        let loaded = load_cli3074_json_core(&synop_base, STATION, FECHA)
            .expect("cargar un archivo inexistente no debe dar error");
        assert!(loaded.is_null(), "si no existe el archivo debe devolver null");
    });
}