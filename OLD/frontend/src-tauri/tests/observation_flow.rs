mod helpers;

use app_lib::json_handler::synoptic::{get_observation_core, save_observation_json_core};
use helpers::with_arca_dir;
use serde_json::{json, Value};
use std::path::PathBuf;

const STATION: &str = "78451";
const FECHA: &str = "2026-08-15";

fn observations_2_horas() -> Value {
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
        },
        "12Z": {
            "ts": "32.0",
            "th": "22.0",
            "pres_est": "1014.0",
            "p3": "1010.0",
            "p24": "1008.0",
            "pres_nmm": "1014.5",
            "punto_rocio": "16.0",
            "meteo_2_1": "12123",
            "meteo_4_irixhvv": "101",
            "meteo_4_1": "33012",
            "meteo_4_6": "03//",
        },
    })
}

fn expected_filepath(base: &std::path::Path) -> PathBuf {
    base.join(STATION)
        .join("2026")
        .join("08")
        .join("7845115082026.json")
}

#[test]
fn save_observation_crea_archivo_en_layout_arca_con_horas_y_calculados() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        let obs = observations_2_horas();

        let res = save_observation_json_core(
            &synop_base,
            STATION.to_string(),
            FECHA.to_string(),
            obs,
            Some("Juan Perez".to_string()),
            None,
            None,
            None,
            |_| None,
        )
        .expect("guardar la observación no debe fallar");

        assert_eq!(res.get("success").map(|s| s.as_str()).unwrap_or(""), "true", "success debe ser true");

        let expected = expected_filepath(&synop_base);
        assert!(
            expected.exists(),
            "el archivo debe existir en el layout ARCA: {}",
            expected.display()
        );
        let filepath = PathBuf::from(res.get("filepath").expect("filepath en respuesta"));
        assert_eq!(filepath, expected, "el filepath reportado debe coincidir con el layout esperado");

        let content = std::fs::read_to_string(&expected).expect("debe leerse el archivo guardado");
        let root: Value = serde_json::from_str(&content).expect("el archivo debe ser JSON válido");

        let horas = root.get("horas").and_then(|h| h.as_object()).expect("debe haber horas");
        assert!(horas.contains_key("00Z"), "debe existir la hora 00Z");
        assert!(horas.contains_key("12Z"), "debe existir la hora 12Z");

        let hora_00 = horas.get("00Z").and_then(|h| h.as_object()).expect("hora 00Z como objeto");
        let datos = hora_00.get("datos").and_then(|d| d.as_object()).expect("datos de 00Z");
        assert_eq!(datos.get("ts").and_then(|v| v.as_str()), Some("30.0"), "el ts debe persistirse en datos");

        let meta = root.get("meta").and_then(|m| m.as_object()).expect("meta");
        assert_eq!(meta.get("estacion").and_then(|v| v.as_str()), Some(STATION), "estacion en meta");
        assert_eq!(meta.get("fecha").and_then(|v| v.as_str()), Some("15082026"), "fecha formateada DDMMYYYY");

        let calculado = hora_00.get("calculado").and_then(|c| c.as_object()).expect("calculado de 00Z");
        assert_eq!(calculado.get("pres_nmm").and_then(|v| v.as_str()), Some("1016.5"), "pres_nmm en calculado");
        assert_eq!(calculado.get("pr").and_then(|v| v.as_str()), Some("15.0"), "punto_rocio mapeado a pr");
    });
}

#[test]
fn get_observation_round_trip_devuelve_horas_y_campos_calculados() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        save_observation_json_core(
            &synop_base,
            STATION.to_string(),
            FECHA.to_string(),
            observations_2_horas(),
            Some("Juan Perez".to_string()),
            None,
            None,
            None,
            |_| None,
        )
        .expect("guardar la observación no debe fallar");

        let loaded = get_observation_core(&synop_base, STATION.to_string(), FECHA.to_string())
            .expect("cargar la observación no debe fallar");

        let hora_00 = loaded.get("00Z").and_then(|h| h.as_object()).expect("debe devolver la hora 00Z");
        assert_eq!(hora_00.get("ts").and_then(|v| v.as_str()), Some("30.0"), "el ts debe hacer round-trip");
        assert_eq!(hora_00.get("pres_est").and_then(|v| v.as_str()), Some("1016.0"), "pres_est round-trip");
        assert_eq!(hora_00.get("pres_nmm").and_then(|v| v.as_str()), Some("1016.5"), "pres_nmm round-trip");
        assert_eq!(hora_00.get("punto_rocio").and_then(|v| v.as_str()), Some("15.0"), "punto_rocio mapeado de vuelta");
        assert_eq!(hora_00.get("meteo_2_1").and_then(|v| v.as_str()), Some("12023"), "campo synop round-trip");

        assert_eq!(hora_00.get("tend_dif").and_then(|v| v.as_str()), Some("04.0"), "dif calculada al cargar");
        assert_eq!(hora_00.get("tend_car").and_then(|v| v.as_str()), Some("3"), "car calculada al cargar");
        assert_eq!(hora_00.get("visibilidad").and_then(|v| v.as_str()), Some("001"), "visibilidad calculada al cargar");

        let hora_12 = loaded.get("12Z").and_then(|h| h.as_object()).expect("debe devolver la hora 12Z");
        assert_eq!(hora_12.get("ts").and_then(|v| v.as_str()), Some("32.0"), "la hora 12Z debe persistir su ts");
    });
}

#[test]
fn sobrescribir_observacion_actualiza_datos_sin_fallo() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        save_observation_json_core(
            &synop_base,
            STATION.to_string(),
            FECHA.to_string(),
            observations_2_horas(),
            Some("Juan Perez".to_string()),
            None,
            None,
            None,
            |_| None,
        )
        .expect("guardado inicial");

        let mut nuevas = observations_2_horas();
        if let Some(hora) = nuevas.get_mut("00Z").and_then(|h| h.as_object_mut()) {
            hora.insert("ts".to_string(), json!("33.0"));
        }

        save_observation_json_core(
            &synop_base,
            STATION.to_string(),
            FECHA.to_string(),
            nuevas,
            Some("Juan Perez".to_string()),
            None,
            None,
            None,
            |_| None,
        )
        .expect("sobrescribir no debe fallar");

        let content = std::fs::read_to_string(expected_filepath(&synop_base)).expect("archivo tras sobrescribir");
        let root: Value = serde_json::from_str(&content).expect("JSON válido tras sobrescribir");
        let horas = root.get("horas").and_then(|h| h.as_object()).expect("horas tras sobrescribir");

        let hora_00 = horas.get("00Z").and_then(|h| h.as_object()).expect("hora 00Z");
        let datos = hora_00.get("datos").and_then(|d| d.as_object()).expect("datos");
        assert_eq!(datos.get("ts").and_then(|v| v.as_str()), Some("33.0"), "el ts nuevo debe reemplazar al viejo");
        assert!(horas.contains_key("12Z"), "la hora no sobrescrita debe permanecer");

        let loaded = get_observation_core(&synop_base, STATION.to_string(), FECHA.to_string())
            .expect("cargar tras sobrescribir");
        assert_eq!(
            loaded.get("00Z").and_then(|h| h.get("ts")).and_then(|v| v.as_str()),
            Some("33.0"),
            "el round-trip debe reflejar el valor actualizado"
        );
    });
}