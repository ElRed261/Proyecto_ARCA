//! F2 unit tests for the verbatim port of `monthly_summary/calculations.rs`
//! (`process_day_data` + shapes from `json_pipeline.rs`).

use crate::monthly::*;
use serde_json::Value;

fn hourly(hora: &str, d: HourlyData) -> HourlyRecord {
    HourlyRecord { hora: hora.to_string(), datos: d }
}

fn hd(
    p_est: Option<f64>,
    p_nmm: Option<f64>,
    rocio: Option<f64>,
    t_vapor: Option<f64>,
    hr: Option<f64>,
    v_dir_deg: Option<f64>,
    v_vel: Option<f64>,
    tmax: Option<f64>,
    tmin: Option<f64>,
    nub: Option<f64>,
) -> HourlyData {
    HourlyData { p_est, p_nmm, rocio, t_vapor, hr, v_dir_deg, v_vel, tmax, tmin, nub }
}

fn full_day() -> DailyObservation {
    // Corpus-like day: 8 Z hours + TMAX/TMIN + cloudiness rows, hour 15Z missing
    // the wind direction (None) on purpose.
    let horarias = vec![
        hourly("06Z", hd(Some(1012.6), Some(1014.2), Some(22.624143756848554), Some(27.359955030153266), Some(80.43463436438854), Some(60.0), Some(3.0), None, None, None)),
        hourly("09Z", hd(Some(1013.1), Some(1014.7), Some(23.1), Some(28.0), Some(82.0), Some(45.0), Some(5.5), None, None, None)),
        hourly("12Z", hd(Some(1011.8), Some(1013.4), Some(24.0), Some(29.1), Some(85.0), Some(70.0), Some(2.0), None, None, None)),
        hourly("15Z", hd(Some(1010.9), Some(1012.5), Some(24.5), Some(29.8), Some(88.0), None, Some(1.5), None, None, None)),
        hourly("18Z", hd(Some(1012.0), Some(1013.6), Some(23.8), Some(29.0), Some(86.0), Some(20.0), Some(4.0), None, None, None)),
        hourly("21Z", hd(Some(1013.4), Some(1015.0), Some(23.2), Some(28.2), Some(83.0), Some(25.0), Some(3.5), None, None, None)),
        hourly("00Z", hd(Some(1014.8), Some(1016.4), Some(22.9), Some(27.9), Some(81.0), Some(30.0), Some(2.5), None, None, None)),
        hourly("03Z", hd(Some(1015.5), Some(1017.1), Some(22.4), Some(27.4), Some(79.5), Some(40.0), Some(3.0), None, None, None)),
        hourly("TMAX", hd(None, None, None, None, None, None, None, Some(31.0), None, None)),
        hourly("TMAX", hd(None, None, None, None, None, None, None, Some(33.5), None, None)),
        hourly("TMIN", hd(None, None, None, None, None, None, None, None, Some(23.0), None)),
        hourly("TMIN", hd(None, None, None, None, None, None, None, None, Some(22.5), None)),
        hourly("filas_nuvosidad_dia", hd(None, None, None, None, None, None, None, None, None, Some(1.0))),
        hourly("filas_nuvosidad_dia", hd(None, None, None, None, None, None, None, None, None, Some(2.5))),
        hourly("filas_nuvosidad_dia", hd(None, None, None, None, None, None, None, None, None, Some(7.0))),
        hourly("filas_nuvosidad_tarde", hd(None, None, None, None, None, None, None, None, None, Some(0.5))),
        hourly("filas_nuvosidad_tarde", hd(None, None, None, None, None, None, None, None, None, Some(3.0))),
        hourly("filas_nuvosidad_tarde", hd(None, None, None, None, None, None, None, None, None, Some(6.0))),
    ];
    DailyObservation {
        meta: ObservationMeta { estacion: "Estación Central".to_string(), fecha: "15052025".to_string() },
        horarias,
        resumen_dia: DaySummary { pp: Some(2.3) },
    }
}

fn approx(a: Option<f64>, b: f64) {
    let v = a.expect("expected Some value");
    assert!((v - b).abs() < 1e-9, "expected {} got {}", b, v);
}

#[test]
fn process_day_data_full_corpus_like_day() {
    let k = process_day_data(&full_day());
    assert_eq!(k.dias, "2025-05-15");
    approx(k.t_max, 33.5);
    approx(k.t_min, 22.5);
    approx(k.t_media, 28.0);
    approx(k.p_nmm_max, 1017.1);
    approx(k.p_nmm_min, 1012.5);
    approx(k.p_nmm_media, 1014.8);
    approx(k.p_est_media, 1013.0);
    approx(k.lluvia, 2.3);
    assert_eq!(k.viento_dir_moda.as_deref(), Some("NNE"));
    approx(k.viento_vel_media, 11.3);
    assert_eq!(k.viento_max_dir.as_deref(), Some("NE 19,8"));
    approx(k.viento_recorrido, 90.0);
    approx(k.nub_dia_media, 3.5);
    approx(k.nub_tarde_media, 3.2);
    approx(k.nub_media, 3.3); // oracle: media from UNROUNDED dia/tarde values
    approx(k.hr_max, 88.0);
    approx(k.hr_min, 80.0);
    approx(k.hr_media, 83.1);
    approx(k.rocio_media, 23.3);
    approx(k.t_vapor_media, 28.3);
}

#[test]
fn process_day_data_empty_day() {
    // Empty-input policy: no records -> None KPIs, wind max falls back to "N/A".
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    assert_eq!(k.dias, "2025-05-15");
    assert_eq!(k.t_max, None);
    assert_eq!(k.t_min, None);
    assert_eq!(k.t_media, None);
    assert_eq!(k.p_nmm_max, None);
    assert_eq!(k.p_nmm_min, None);
    assert_eq!(k.p_nmm_media, None);
    assert_eq!(k.p_est_media, None);
    assert_eq!(k.lluvia, None);
    assert_eq!(k.viento_dir_moda, None);
    assert_eq!(k.viento_vel_media, None);
    assert_eq!(k.viento_max_dir, Some("N/A".to_string()));
    assert_eq!(k.viento_recorrido, None);
    assert_eq!(k.nub_dia_media, None);
    assert_eq!(k.nub_tarde_media, None);
    assert_eq!(k.nub_media, None);
    assert_eq!(k.hr_max, None);
    assert_eq!(k.hr_min, None);
    assert_eq!(k.hr_media, None);
    assert_eq!(k.rocio_media, None);
    assert_eq!(k.t_vapor_media, None);
}

#[test]
fn process_day_data_non_z_hours_ignored() {
    // Unknown hora labels fall into the catch-all branch: no panic, no data.
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("05Z", hd(Some(1012.0), Some(1014.0), None, None, None, None, None, None, None, None)),
            hourly("FOO", hd(None, None, None, None, None, None, None, Some(99.0), Some(1.0), Some(8.0))),
        ],
        resumen_dia: DaySummary { pp: Some(0.0) },
    };
    let k = process_day_data(&obs);
    assert_eq!(k.t_max, None);
    assert_eq!(k.t_min, None);
    assert_eq!(k.p_est_media, None);
    assert_eq!(k.lluvia, Some(0.0));
}

#[test]
fn process_day_data_safe_f64_filters_non_finite() {
    // NaN/inf must behave like missing values (oracle safe_f64).
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("06Z", hd(Some(f64::NAN), Some(f64::INFINITY), Some(f64::NAN), Some(f64::NEG_INFINITY), Some(f64::NAN), Some(f64::NAN), Some(f64::NAN), None, None, None)),
            hourly("09Z", hd(Some(1010.0), Some(1012.0), None, None, None, None, None, None, None, None)),
        ],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    approx(k.p_est_media, 1010.0);
    approx(k.p_nmm_max, 1012.0);
    approx(k.p_nmm_min, 1012.0);
    assert_eq!(k.rocio_media, None);
    assert_eq!(k.t_vapor_media, None);
    assert_eq!(k.hr_max, None);
    assert_eq!(k.viento_dir_moda, None); // no valid speeds
    assert_eq!(k.viento_max_dir, Some("N/A".to_string())); // no valid velocity
}

#[test]
fn round_half_up_is_not_bankers_rounding() {
    // Oracle rounds half UP (floor-based), not half-to-even.
    assert_eq!(round_half_up(2.45, 1), 2.5);
    assert_eq!(round_half_up(2.44, 1), 2.4);
    assert_eq!(round_half_up(-2.45, 1), -2.5); // away from zero via signum
    assert_eq!(round_half_up(0.05, 0), 0.0);
    assert_eq!(round_half_up(2.5, 0), 3.0);
    assert_eq!(round_half_up(11.25, 1), 11.3);
}

#[test]
fn degrees_to_cardinal_boundaries() {
    assert_eq!(degrees_to_cardinal(0.0), "CALMA");
    assert_eq!(degrees_to_cardinal(360.0), "N");
    assert_eq!(degrees_to_cardinal(11.25), "NNE"); // .round() is half away from zero
    assert_eq!(degrees_to_cardinal(45.0), "NE");
    assert_eq!(degrees_to_cardinal(90.0), "E");
    assert_eq!(degrees_to_cardinal(202.5), "SSW");
    assert_eq!(degrees_to_cardinal(337.5), "NNW");
    assert_eq!(degrees_to_cardinal(348.75), "N"); // 15.5.round()=16 -> %16 = 0
    assert_eq!(degrees_to_cardinal(-1.0), "N/A");
    assert_eq!(degrees_to_cardinal(361.0), "N/A");
}

#[test]
fn wind_direction_mode_rules() {
    // Dominant direction needs >= 3 occurrences
    let mut dirs: Vec<Option<f64>> = vec![Some(60.0), Some(60.0), Some(70.0), Some(60.0)];
    let speeds = vec![Some(3.0); 4];
    assert_eq!(wind_direction_mode(&dirs, &speeds).as_deref(), Some("ENE"));
    // Fewer than 3 -> VRB
    dirs = vec![Some(60.0), Some(45.0)];
    assert_eq!(wind_direction_mode(&dirs, &speeds).as_deref(), Some("VRB"));
    // Calm: mean speed < 0.1
    let calm_speeds = vec![Some(0.05); 4];
    assert_eq!(wind_direction_mode(&dirs, &calm_speeds).as_deref(), Some("CALMA"));
    // No valid speeds -> None
    let no_speeds = vec![Some(f64::NAN); 2];
    assert_eq!(wind_direction_mode(&dirs, &no_speeds), None);
    // CALMA and N/A cards are excluded from the frequency race
    let mixed: Vec<Option<f64>> = vec![Some(0.0), Some(999.0), Some(60.0), Some(60.0)];
    let s = vec![Some(5.0); 4];
    assert_eq!(wind_direction_mode(&mixed, &s).as_deref(), Some("VRB"));
}

#[test]
fn wind_max_tie_breaks_first_occurrence() {
    // Max velocity found at the FIRST of equal maxima (strict > comparison).
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("06Z", hd(None, None, None, None, None, Some(90.0), Some(5.0), None, None, None)),
            hourly("09Z", hd(None, None, None, None, None, Some(180.0), Some(5.0), None, None, None)),
        ],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    assert_eq!(k.viento_max_dir, Some("E 18,0".to_string()));
}

#[test]
fn wind_max_without_direction_is_na() {
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("06Z", hd(None, None, None, None, None, None, Some(5.0), None, None, None)),
        ],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    assert_eq!(k.viento_max_dir, Some("N/A 18,0".to_string()));
}

#[test]
fn nubosidad_fallback_branch_when_no_filas() {
    // No filas_nuvosidad_*: mean over nub values of the Z hours, same value for
    // dia/media and tarde stays None (oracle fallback branch).
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("06Z", hd(None, None, None, None, None, None, None, None, None, Some(2.0))),
            hourly("09Z", hd(None, None, None, None, None, None, None, None, None, Some(5.0))),
        ],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    approx(k.nub_dia_media, 3.5);
    assert_eq!(k.nub_tarde_media, None);
    approx(k.nub_media, 3.5);
}

#[test]
fn nubosidad_filas_with_invalid_members() {
    // NaN members are skipped; sum still divided by fixed 3.0 (oracle policy).
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("filas_nuvosidad_dia", hd(None, None, None, None, None, None, None, None, None, Some(f64::NAN))),
            hourly("filas_nuvosidad_dia", hd(None, None, None, None, None, None, None, None, None, Some(3.0))),
            hourly("filas_nuvosidad_dia", hd(None, None, None, None, None, None, None, None, None, Some(6.0))),
        ],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    approx(k.nub_dia_media, 3.0); // (3+6)/3
    assert_eq!(k.nub_tarde_media, None);
    assert_eq!(k.nub_media, None); // both branches needed for the media
}

#[test]
fn nubosidad_filas_only_tarde() {
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15052025".to_string() },
        horarias: vec![
            hourly("filas_nuvosidad_tarde", hd(None, None, None, None, None, None, None, None, None, Some(1.5))),
            hourly("filas_nuvosidad_tarde", hd(None, None, None, None, None, None, None, None, None, Some(4.5))),
            hourly("filas_nuvosidad_tarde", hd(None, None, None, None, None, None, None, None, None, Some(7.5))),
        ],
        resumen_dia: DaySummary { pp: None },
    };
    let k = process_day_data(&obs);
    assert_eq!(k.nub_dia_media, None);
    approx(k.nub_tarde_media, 4.5);
    assert_eq!(k.nub_media, None);
}

#[test]
fn dias_formats_only_8_char_fechas() {
    let obs = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "15032024".to_string() },
        horarias: vec![],
        resumen_dia: DaySummary { pp: None },
    };
    assert_eq!(process_day_data(&obs).dias, "2024-03-15");

    let obs2 = DailyObservation {
        meta: ObservationMeta { estacion: "X".to_string(), fecha: "1503".to_string() },
        horarias: vec![],
        resumen_dia: DaySummary { pp: None },
    };
    assert_eq!(process_day_data(&obs2).dias, "1503");
}

// =============================================================================
// Serialization shape (oracle JSON column names)
// =============================================================================

#[test]
fn daily_kpis_serializes_oracle_column_names() {
    let k = process_day_data(&full_day());
    let v: Value = serde_json::to_value(&k).unwrap();
    let obj = v.as_object().unwrap();
    for key in [
        "Dias",
        "Mayor temperatura máxima",
        "Menor temperatura minima",
        "Media temperatura",
        "MAxima presión nivel medio del mar",
        "Minima presión nivel medio del mar",
        "Media presión nivel medio del mar",
        "Media presion en la estación",
        "Lluvia",
        "Dirección del viento",
        "Velocidad media del viento",
        "Velocidad máxima y direccion",
        "Recorrido del viento",
        "Nuvocidad dia",
        "Nuvocidad noche",
        "Media de nuvocidad",
        "Humedad maxima",
        "Humedad minima",
        "Humedad media",
        "Punto de rocio",
        "Tensión de vapor",
    ] {
        assert!(obj.contains_key(key), "missing column {}", key);
    }
}

#[test]
fn daily_observation_deserializes_corpus_shape() {
    // The corpus daily JSON shape must deserialize into DailyObservation
    // (missing optional HourlyData fields default via Option; extended fields
    // are simply absent in basic files).
    let raw = r#"{
        "meta": {"estacion": "78486", "fecha": "08122025"},
        "horarias": [
            {"hora": "06Z", "datos": {"p_est": 1012.6, "p_nmm": 1014.2, "rocio": 22.6, "t_vapor": 27.3, "hr": 80.4, "v_dir_deg": 60, "v_vel": 3.0}},
            {"hora": "TMAX", "datos": {"tmax": 31.0}},
            {"hora": "TMIN", "datos": {"tmin": 22.0}}
        ],
        "resumen_dia": {"pp": 2.3}
    }"#;
    let obs: DailyObservation = serde_json::from_str(raw).unwrap();
    assert_eq!(obs.meta.fecha, "08122025");
    assert_eq!(obs.horarias.len(), 3);
    let k = process_day_data(&obs);
    assert_eq!(k.dias, "2025-12-08");
    approx(k.t_max, 31.0);
    approx(k.t_min, 22.0);
    approx(k.t_media, 26.5);
}
