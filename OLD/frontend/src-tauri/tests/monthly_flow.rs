mod helpers;

use app_lib::json_handler::synoptic::save_observation_json_core;
use app_lib::monthly_summary::commands::ms_load_station_month_core;
use helpers::with_arca_dir;
use serde_json::{json, Value};
use std::path::Path;

const STATION: &str = "78451";

fn observations_dia(ts: &str) -> Value {
    let mut horas = serde_json::Map::new();
    for hora in ["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"] {
        horas.insert(
            hora.to_string(),
            json!({
                "ts": ts,
                "th": "20.0",
                "pres_est": "1015.0",
                "p3": "1012.0",
                "p24": "1010.0",
                "viento_dir": "90.0",
                "viento_vel": "5.0",
                "t_max": "30.5",
                "t_min": "22.0",
                "pres_nmm": "1015.5",
                "punto_rocio": "15.0",
                "tension_vapor": "16.0",
                "humedad_relativa": "60.0",
                "meteo_2_1": "12023",
                "meteo_4_irixhvv": "101",
                "meteo_4_1": "31018",
                "meteo_4_6": "02//",
            }),
        );
    }
    Value::Object(horas)
}

fn save_dia(synop_base: &Path, fecha: &str) {
    save_observation_json_core(
        synop_base,
        STATION.to_string(),
        fecha.to_string(),
        observations_dia("28.0"),
        Some("Juan Perez".to_string()),
        None,
        None,
        None,
        |_| None,
    )
    .expect("guardar día sinóptico no debe fallar");
}

#[test]
fn ms_load_station_month_core_agrega_kpis_de_dos_dias_reales() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        save_dia(&synop_base, "2026-08-14");
        save_dia(&synop_base, "2026-08-15");

        let summary_dir = base.join("sumario");
        let doc = ms_load_station_month_core(&synop_base, &summary_dir, STATION, 2026, 8)
            .expect("generar resumen mensual no debe fallar");

        assert_eq!(doc.meta.estacion, STATION, "la estación del resumen debe ser la guardada");
        assert_eq!(doc.meta.periodo, "08/2026", "el periodo debe derivarse de los días");
        assert_eq!(doc.meta.total_dias, 2, "debe haber un día por archivo JSON");
        assert_eq!(doc.datos.len(), 2, "debe haber un conjunto de KPIs por día");

        let dia_14 = &doc.datos[0];
        assert_eq!(dia_14.dias, "2026-08-14", "primer día debe quedar ordenado cronológicamente");
        assert_eq!(dia_14.t_max, Some(30.5), "Tmax 30.5 debe reflejarse en el KPI");
        assert_eq!(dia_14.t_min, Some(22.0), "Tmin 22.0 debe reflejarse en el KPI");
        assert_eq!(dia_14.p_nmm_max, Some(1015.5), "presión nmm máxima del día");
        assert_eq!(dia_14.p_nmm_min, Some(1015.5), "presión nmm mínima del día");
        assert_eq!(dia_14.p_nmm_media, Some(1015.5), "presión nmm media del día");
        assert_eq!(dia_14.p_est_media, Some(1015.0), "presión en estación media");
        assert_eq!(dia_14.nub_media, Some(3.0), "nubosidad media derivada de Nddff");
        assert_eq!(dia_14.rocio_media, Some(15.0), "rocio medio derivado de calculado");

        let dia_15 = &doc.datos[1];
        assert_eq!(dia_15.dias, "2026-08-15", "segundo día en orden");
        assert_eq!(dia_15.t_media, Some(26.3), "media (30.5 + 22.0) / 2");

        assert!(
            summary_dir.join("resumen_78451_082026.json").exists(),
            "el resumen debe persistirse en el directorio de historial"
        );
    });
}

#[test]
fn ms_load_station_month_core_falla_sin_datos() {
    with_arca_dir(|base| {
        let synop_base = base.join("synop");
        let summary_dir = base.join("sumario");
        let err = ms_load_station_month_core(&synop_base, &summary_dir, STATION, 2026, 8)
            .expect_err("sin datos debe fallar con error descriptivo");
        assert!(
            err.contains("No se encontraron datos"),
            "debe indicar que no hay datos, error: {}",
            err
        );
    });
}