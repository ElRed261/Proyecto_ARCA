use serde_json::Value;
use super::json_pipeline::{DailyObservation, ObservationMeta, HourlyRecord, HourlyData, DaySummary};

fn parse_f64_opt(val: Option<&Value>) -> Option<f64> {
    match val {
        Some(Value::Number(n)) => n.as_f64(),
        Some(Value::String(s)) => {
            let cleaned = s.trim().replace(',', ".");
            cleaned.parse::<f64>().ok()
        }
        _ => None,
    }
}

fn get_nubosidad_from_nddff(hora_data_obj: &serde_json::Map<String, Value>) -> Option<f64> {
    if let Some(synop) = hora_data_obj.get("synop").and_then(|s| s.as_object()) {
        if let Some(nddff) = synop.get("Nddff").and_then(|v| v.as_str()) {
            if !nddff.is_empty() {
                if let Some(n_char) = nddff.chars().next() {
                    if let Some(d) = n_char.to_digit(10) {
                        if d <= 9 {
                            return Some(d as f64);
                        }
                    }
                }
            }
        }
    }
    None
}

fn get_nubosidad_fallback(hora_data_obj: &serde_json::Map<String, Value>) -> Option<f64> {
    if let Some(synop) = hora_data_obj.get("synop").and_then(|s| s.as_object()) {
        if let Some(g8) = synop.get("8NhCLCMCH").and_then(|v| v.as_str()) {
            if g8.len() >= 2 {
                if let Some(nh_char) = g8.chars().nth(1) {
                    if let Some(d) = nh_char.to_digit(10) {
                        if d <= 8 {
                            return Some(d as f64);
                        }
                    }
                }
            }
        }
    }
    None
}

fn get_nubosidad_for_ast_hour(
    ast_hour: &str,
    utc_hour: &str,
    horas_map: Option<&serde_json::Map<String, Value>>,
    cli4074: Option<&serde_json::Map<String, Value>>,
) -> Option<f64> {
    // 1. Try cli4074 row (the row index matches the local AST hour as string)
    if let Some(row_data) = cli4074.and_then(|c| c.get(ast_hour)).and_then(|r| r.as_object()) {
        if let Some(val) = parse_f64_opt(row_data.get("nubosidad")) {
            return Some(val);
        }
    }
    
    // 2. Try horas UTC map
    if let Some(h_obj) = horas_map.and_then(|m| m.get(utc_hour)).and_then(|h| h.as_object()) {
        return get_nubosidad_from_nddff(h_obj).or_else(|| get_nubosidad_fallback(h_obj));
    }
    
    None
}

pub fn adapt_synoptic_json(value: Value) -> Result<DailyObservation, String> {
    let root = value.as_object().ok_or("Root is not a JSON object")?;

    // 1. Meta
    let meta_obj = root.get("meta").and_then(|m| m.as_object()).ok_or("Meta is missing or not an object")?;
    let estacion = meta_obj.get("estacion")
        .and_then(|e| e.as_str())
        .ok_or("meta.estacion is missing or not a string")?
        .to_string();
    
    let fecha_raw = meta_obj.get("fecha")
        .and_then(|f| f.as_str())
        .ok_or("meta.fecha is missing or not a string")?;
    
    // Adapt DDMMYY -> DDMMYYYY
    let fecha = if fecha_raw.len() == 6 {
        let yy = &fecha_raw[4..6];
        if let Ok(year_val) = yy.parse::<i32>() {
            let century = if year_val >= 70 { "19" } else { "20" };
            format!("{}{}{}", &fecha_raw[0..4], century, yy)
        } else {
            fecha_raw.to_string()
        }
    } else {
        fecha_raw.to_string()
    };

    let meta = ObservationMeta { estacion, fecha };

    // 2. Horarias
    let mut horarias = Vec::new();
    
    let horas_map = root.get("horas").and_then(|h| h.as_object());
    let cli4074 = root.get("cli4074").and_then(|c| c.as_object());
    let cli3074 = root.get("cli3074").and_then(|c| c.as_object());

    // Main 8 synoptic hours
    let hours_config = [
        ("06Z", "2"),
        ("09Z", "5"),
        ("12Z", "8"),
        ("15Z", "11"),
        ("18Z", "14"),
        ("21Z", "17"),
        ("00Z", "20"),
        ("03Z", "23"),
    ];

    for &(hour, row_idx) in &hours_config {
        let mut p_est = None;
        let mut p_nmm = None;
        let mut rocio = None;
        let mut t_vapor = None;
        let mut hr = None;
        let mut v_dir_deg = None;
        let mut v_vel = None;

        // Try reading from hours block
        if let Some(h_obj) = horas_map.and_then(|m| m.get(hour)).and_then(|h| h.as_object()) {
            if let Some(datos) = h_obj.get("datos").and_then(|d| d.as_object()) {
                p_est = parse_f64_opt(datos.get("pres_est"));
                v_dir_deg = parse_f64_opt(datos.get("viento_dir"));
                v_vel = parse_f64_opt(datos.get("viento_vel"));
            }
            if let Some(calc_obj) = h_obj.get("calculado").and_then(|c| c.as_object()) {
                p_nmm = parse_f64_opt(calc_obj.get("pres_nmm"));
                rocio = parse_f64_opt(calc_obj.get("pr"));
                t_vapor = parse_f64_opt(calc_obj.get("tv"));
                hr = parse_f64_opt(calc_obj.get("hr"));
            }
        }

        // Get cloudiness (tries cli4074, then Nddff, then fallback)
        let nub = get_nubosidad_for_ast_hour(row_idx, hour, horas_map, cli4074);

        // Try reading from cli3074 (hourly inputs override if hours block is empty)
        if let Some(row_data) = cli3074.and_then(|c| c.get(row_idx)).and_then(|r| r.as_object()) {
            if p_est.is_none() { p_est = parse_f64_opt(row_data.get("pres_est")); }
            if p_nmm.is_none() { p_nmm = parse_f64_opt(row_data.get("pres_nmm")); }
            if rocio.is_none() { rocio = parse_f64_opt(row_data.get("hum_ptor")); }
            if t_vapor.is_none() { t_vapor = parse_f64_opt(row_data.get("hum_tvap")); }
            if hr.is_none() { hr = parse_f64_opt(row_data.get("hum_hr")); }
            if v_dir_deg.is_none() { v_dir_deg = parse_f64_opt(row_data.get("viento_dir")); }
            if v_vel.is_none() { v_vel = parse_f64_opt(row_data.get("viento_vel")); }
        }

        horarias.push(HourlyRecord {
            hora: hour.to_string(),
            datos: HourlyData {
                p_est,
                p_nmm,
                rocio,
                t_vapor,
                hr,
                v_dir_deg,
                v_vel,
                tmax: None,
                tmin: None,
                nub,
            },
        });
    }

    // Add TMAX / TMIN records
    // Hours where they can be recorded: 06Z, 12Z, 18Z, 00Z (rows 2, 8, 14, 20)
    let temp_config = [
        ("06Z", "2"),
        ("12Z", "8"),
        ("18Z", "14"),
        ("00Z", "20"),
    ];

    for &(hour, row_idx) in &temp_config {
        let mut tmax = None;
        let mut tmin = None;

        // Try reading from cli4074
        if let Some(row_data) = cli4074.and_then(|c| c.get(row_idx)).and_then(|r| r.as_object()) {
            tmax = parse_f64_opt(row_data.get("temp_max"));
            tmin = parse_f64_opt(row_data.get("temp_min"));
        }

        // Fallback to hours block
        if let Some(h_obj) = horas_map.and_then(|m| m.get(hour)).and_then(|h| h.as_object()) {
            if let Some(datos) = h_obj.get("datos").and_then(|d| d.as_object()) {
                if tmax.is_none() { tmax = parse_f64_opt(datos.get("Tmax")); }
                if tmin.is_none() { tmin = parse_f64_opt(datos.get("Tmin")); }
            }
        }

        if let Some(val) = tmax {
            horarias.push(HourlyRecord {
                hora: "TMAX".to_string(),
                datos: HourlyData {
                    tmax: Some(val),
                    ..Default::default()
                },
            });
        }
        if let Some(val) = tmin {
            horarias.push(HourlyRecord {
                hora: "TMIN".to_string(),
                datos: HourlyData {
                    tmin: Some(val),
                    ..Default::default()
                },
            });
        }
    }

    // Add cloudiness dia/tarde records
    // Day (mañana): rows 5, 8, 11 (which correspond to local AST hours 5, 8, 11) -> UTC hours 09Z, 12Z, 15Z
    let cloud_day_config = [("5", "09Z"), ("8", "12Z"), ("11", "15Z")];
    for &(row_idx, utc_hour) in &cloud_day_config {
        if let Some(val) = get_nubosidad_for_ast_hour(row_idx, utc_hour, horas_map, cli4074) {
            horarias.push(HourlyRecord {
                hora: "filas_nuvosidad_dia".to_string(),
                datos: HourlyData {
                    nub: Some(val),
                    ..Default::default()
                },
            });
        }
    }

    // Afternoon (tarde): rows 14, 17, 20 (local AST hours 14, 17, 20) -> UTC hours 18Z, 21Z, 00Z
    let cloud_afternoon_config = [("14", "18Z"), ("17", "21Z"), ("20", "00Z")];
    for &(row_idx, utc_hour) in &cloud_afternoon_config {
        if let Some(val) = get_nubosidad_for_ast_hour(row_idx, utc_hour, horas_map, cli4074) {
            horarias.push(HourlyRecord {
                hora: "filas_nuvosidad_tarde".to_string(),
                datos: HourlyData {
                    nub: Some(val),
                    ..Default::default()
                },
            });
        }
    }

    // 3. Precipitation pp (resumen_dia)
    // Read from 12Z LL_24h or LL
    let mut pp = None;
    if let Some(h12) = horas_map.and_then(|m| m.get("12Z")).and_then(|h| h.as_object()) {
        if let Some(datos) = h12.get("datos").and_then(|d| d.as_object()) {
            pp = parse_f64_opt(datos.get("LL_24h"));
            if pp.is_none() {
                pp = parse_f64_opt(datos.get("LL"));
            }
        }
    }

    let resumen_dia = DaySummary { pp };

    Ok(DailyObservation {
        meta,
        horarias,
        resumen_dia,
    })
}
