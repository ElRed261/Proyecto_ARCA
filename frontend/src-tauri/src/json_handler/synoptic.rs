use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use tauri::AppHandle;
use super::utils::*;

// Mapeo de campos del frontend a nombres SYNOP OMM
const FRONTEND_TO_SYNOP: &[(&str, &str)] = &[
    // Grupo 2
    ("meteo_2_1", "YYGGiw"),
    // Grupo 4
    ("meteo_4_irixhvv", "IrIXHVV"),
    ("meteo_4_1", "Nddff"),
    ("meteo_4_6", "7wwW1W2"),
    // Grupo 6
    ("meteo_6_0", "8NhCLCMCH"),
    ("meteo_6_2", "0CSDL DM DH"),
    ("meteo_6_3", "1snTxTxTx"),
    ("meteo_6_4", "2snTnTnTn"),
    ("meteo_6_5", "3Ejjj"),
    ("meteo_6_6", "5EEEjE"),
    // Grupo 8
    ("meteo_8_0", "5nFnFnFn"),
    ("meteo_8_1", "56DLDMDH"),
    ("meteo_8_3", "6RRRtr"),
    ("meteo_8_4", "7R24R24R24R24"),
    ("meteo_8_5", "8NsChshs_1"),
    ("meteo_8_6", "8NsChshs_2"),
    ("extra_8ns_1", "8NsChshs_3"),
    ("extra_8ns_2", "8NsChshs_4"),
    // Grupos 9sp (serie 10 a 16)
    ("meteo_10_0", "8NsChshs_5"),
    ("meteo_10_1", "8NsChshs_6"),
    ("meteo_10_2", "9spspsp_1"),
    ("meteo_10_3", "9spspsp_2"),
    ("meteo_10_4", "9spspsp_3"),
    ("meteo_10_5", "9spspsp_4"),
    ("meteo_10_6", "9spspsp_5"),
    ("meteo_12_0", "9spspsp_6"),
    ("meteo_12_1", "9spspsp_7"),
    ("meteo_12_2", "9spspsp_8"),
    ("meteo_12_3", "9spspsp_9"),
    ("meteo_12_4", "9spspsp_10"),
    ("meteo_12_5", "9spspsp_11"),
    ("meteo_12_6", "9spspsp_12"),
    ("meteo_14_0", "9spspsp_13"),
    ("meteo_14_1", "9spspsp_14"),
    ("meteo_14_2", "9spspsp_15"),
    ("meteo_14_3", "9spspsp_16"),
    ("meteo_14_4", "9spspsp_17"),
    ("meteo_14_5", "9spspsp_18"),
    ("meteo_14_6", "9spspsp_19"),
    ("meteo_16_0", "9spspsp_20"),
    ("meteo_16_1", "9spspsp_21"),
    ("meteo_16_2", "9spspsp_22"),
    ("meteo_16_3", "9spspsp_23"),
    ("meteo_16_4", "9spspsp_24"),
];

// Función helper para convertir nombre frontend a SYNOP
pub(crate) fn to_synop_name(frontend_name: &str) -> String {
    for (from, to) in FRONTEND_TO_SYNOP.iter() {
        if *from == frontend_name {
            return to.to_string();
        }
    }
    frontend_name.to_string()
}

// Map SYNOP names to frontend field names
pub(crate) fn to_frontend_name(synop_name: &str) -> String {
    let mapping = [
        ("YYGGiw", "meteo_2_1"),
        ("IrIXHVV", "meteo_4_irixhvv"),
        ("Nddff", "meteo_4_1"),
        ("7wwW1W2", "meteo_4_6"),
        ("8NhCLCMCH", "meteo_6_0"),
        ("0CSDL DM DH", "meteo_6_2"),
        ("1snTxTxTx", "meteo_6_3"),
        ("2snTnTnTn", "meteo_6_4"),
        ("3Ejjj", "meteo_6_5"),
        ("5EEEjE", "meteo_6_6"),
        ("5nFnFnFn", "meteo_8_0"),
        ("56DLDMDH", "meteo_8_1"),
        ("6RRRtr", "meteo_8_3"),
        ("7R24R24R24R24", "meteo_8_4"),
        ("8NsChshs_1", "meteo_8_5"),
        ("8NsChshs_2", "meteo_8_6"),
        ("8NsChshs_3", "extra_8ns_1"),
        ("8NsChshs_4", "extra_8ns_2"),
        ("8NsChshs_5", "meteo_10_0"),
        ("8NsChshs_6", "meteo_10_1"),
    ];
    for (s, f) in mapping.iter() {
        if *s == synop_name {
            return f.to_string();
        }
    }
    synop_name.to_string()
}

/// Tabla de conversión de visibilidad desde VV
pub(crate) fn get_visibilidad_from_irixhv(irixhv: &str) -> String {
    let table: [(&str, &str); 75] = [
        ("00", "000"), ("01", "001"), ("02", "002"), ("03", "003"), ("04", "004"),
        ("05", "005"), ("06", "006"), ("07", "007"), ("08", "008"), ("09", "009"),
        ("10", "010"), ("11", "011"), ("12", "012"), ("13", "013"), ("14", "014"),
        ("15", "015"), ("16", "016"), ("17", "017"), ("18", "018"), ("19", "019"),
        ("20", "020"), ("21", "021"), ("22", "022"), ("23", "023"), ("24", "024"),
        ("25", "025"), ("26", "026"), ("27", "027"), ("28", "028"), ("29", "029"),
        ("30", "030"), ("31", "031"), ("32", "032"), ("33", "033"), ("34", "034"),
        ("35", "035"), ("36", "036"), ("37", "037"), ("38", "038"), ("39", "039"),
        ("40", "040"), ("41", "041"), ("42", "042"), ("43", "043"), ("44", "044"),
        ("45", "045"), ("46", "046"), ("47", "047"), ("48", "048"), ("49", "049"),
        ("56", "060"), ("57", "070"), ("58", "080"), ("59", "090"), ("60", "100"),
        ("61", "110"), ("62", "120"), ("63", "130"), ("64", "140"), ("65", "150"),
        ("66", "160"), ("67", "170"), ("68", "180"), ("69", "190"), ("70", "200"),
        ("71", "210"), ("72", "220"), ("73", "230"), ("74", "240"), ("75", "250"),
        ("76", "260"), ("77", "270"), ("78", "280"), ("79", "290"), ("80", "300"),
    ];
    if irixhv.len() >= 2 {
        let code = &irixhv[irixhv.len() - 2..];
        for (k, v) in table.iter() {
            if *k == code {
                return v.to_string();
            }
        }
    }
    String::new()
}

/// Formatear DIF (diferencia de presión) al formato "00.0"
pub(crate) fn format_dif(dif_value: &str) -> String {
    if dif_value.is_empty() {
        return String::new();
    }
    if dif_value.len() == 4 && dif_value.contains('.') {
        return dif_value.to_string();
    }
    if dif_value.len() == 3 {
        let chars: Vec<char> = dif_value.chars().collect();
        return format!("{}{}.{}", chars[0], chars[1], chars[2]);
    }
    if dif_value.len() == 4 {
        let chars: Vec<char> = dif_value.chars().collect();
        return format!("{}{}.{}{}", chars[0], chars[1], chars[2], chars[3]);
    }
    dif_value.to_string()
}

/// Calcular DIF (diferencia de presión) desde presión de estación y P3
pub(crate) fn calc_dif(pres_est: &str, p3: &str) -> String {
    if let (Ok(pe), Ok(p)) = (pres_est.parse::<f64>(), p3.parse::<f64>()) {
        let dif = (pe - p).abs();
        return format!("{:04.1}", dif);
    }
    String::new()
}

/// Calcular CAR desde la diferencia de presión
pub(crate) fn calc_car(pres_est: &str, p3: &str) -> String {
    if let (Ok(pe), Ok(p)) = (pres_est.parse::<f64>(), p3.parse::<f64>()) {
        let dif = pe - p;
        let abs_dif = dif.abs();

        if dif == 0.0 {
            return "4".to_string();
        }

        if dif > 0.0 {
            if (0.1..=0.5).contains(&abs_dif) { return "0".to_string(); }
            if (0.6..=1.4).contains(&abs_dif) { return "1".to_string(); }
            if (1.5..=1.9).contains(&abs_dif) { return "2".to_string(); }
            if abs_dif >= 2.0 { return "3".to_string(); }
        } else {
            if (0.1..=0.5).contains(&abs_dif) { return "5".to_string(); }
            if (0.6..=1.4).contains(&abs_dif) { return "6".to_string(); }
            if (1.5..=1.9).contains(&abs_dif) { return "7".to_string(); }
            if abs_dif >= 2.0 { return "8".to_string(); }
        }
    }
    String::new()
}

/// Calcular tiempo presente
pub(crate) fn calc_tiempo_presente(seven_ww: &str, nddff_current: &str, nddff_prev: &str) -> String {
    if seven_ww.len() >= 3 {
        let ww_chars = &seven_ww[1..3];
        if !ww_chars.contains('/') {
            return ww_chars.to_string();
        }
    }

    if !nddff_current.is_empty() && !nddff_prev.is_empty() {
        let curr = nddff_current.chars().next().unwrap_or('0');
        let prev = nddff_prev.chars().next().unwrap_or('0');

        if curr != '/' && prev != '/' {
            return if curr > prev {
                "01".to_string()
            } else if curr == prev {
                "02".to_string()
            } else {
                "03".to_string()
            };
        }
    }

    String::new()
}

/// Obtener la hora sinóptica anterior (3 horas antes)
pub(crate) fn get_prev_hour(hora: &str) -> &'static str {
    match hora {
        "09Z" => "06Z",
        "12Z" => "09Z",
        "15Z" => "12Z",
        "18Z" => "15Z",
        "21Z" => "18Z",
        "00Z" => "21Z",
        "03Z" => "00Z",
        "06Z" => "03Z",
        _ => "",
    }
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
pub fn save_observation_json(
    app_handle: AppHandle,
    station_code: String,
    fecha: String,
    observations: Value,
    observer_name: Option<String>,
    cli3074: Option<Value>,
    cli4074: Option<Value>,
    cli5074: Option<Value>,
) -> Result<HashMap<String, String>, String> {
    let base_dir = get_arca_base_dir(&app_handle, crate::infrastructure::storage::SYNOP_MODULE);
    let station = station_code.clone();
    save_observation_json_core(
        &base_dir,
        station_code,
        fecha,
        observations,
        observer_name,
        cli3074,
        cli4074,
        cli5074,
        move |filepath| create_backup(filepath, &station, &app_handle),
    )
}

// pub para tests de integración
#[allow(clippy::too_many_arguments)]
pub fn save_observation_json_core(
    base_dir: &Path,
    station_code: String,
    fecha: String,
    observations: Value,
    observer_name: Option<String>,
    cli3074: Option<Value>,
    cli4074: Option<Value>,
    cli5074: Option<Value>,
    backup: impl FnOnce(&Path) -> Option<String>,
) -> Result<HashMap<String, String>, String> {
    validate_inputs(&station_code, &fecha)?;
    let (year, month) = parse_date_parts(&fecha);

    let dir_path = ensure_arca_dirs_with_station(base_dir, &station_code, &year, &month)?;

    let fecha_formatted = format_date_for_filename(&fecha);
    let filename = format!("{}{}.json", station_code, fecha_formatted);
    let filepath = dir_path.join(&filename);

    let backup_path = backup(&filepath).unwrap_or_default();

    // Leer archivo existente si existe para no borrar datos de CLI
    let mut root_map = if filepath.exists() {
        let existing_data = fs::read_to_string(&filepath).map_err(|e| e.to_string())?;
        let val: Value = serde_json::from_str(&existing_data).map_err(|e| e.to_string())?;
        val.as_object().cloned().unwrap_or_else(serde_json::Map::new)
    } else {
        serde_json::Map::new()
    };

    // Meta
    let mut meta = serde_json::Map::new();
    meta.insert("estacion".to_string(), Value::String(station_code.clone()));
    meta.insert("fecha".to_string(), Value::String(fecha_formatted.clone()));
    if let Some(ref name) = observer_name {
        meta.insert("observador".to_string(), Value::String(name.clone()));
    }
    meta.insert(
        "ultima_actualizacion".to_string(),
        Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
    );
    root_map.insert("meta".to_string(), Value::Object(meta));

    // Horas
    let mut horas_map = serde_json::Map::new();

    if let Some(horas_obj) = observations.as_object() {
        for (hora_key, hora_data) in horas_obj {
            if let Some(hora_data_obj) = hora_data.as_object() {
                let mut hora_structure = serde_json::Map::new();

                // Datos
                let mut datos = serde_json::Map::new();
                if let Some(v) = hora_data_obj.get("ts") { datos.insert("ts".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("th") { datos.insert("th".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("pres_est") { datos.insert("pres_est".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("p3") { datos.insert("p3".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("p24") { datos.insert("p24".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("viento_dir") { datos.insert("viento_dir".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("viento_vel") { datos.insert("viento_vel".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("visibilidad") { datos.insert("visibilidad".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("t_max") { datos.insert("Tmax".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("t_min") { datos.insert("Tmin".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("ll") { datos.insert("LL".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("t_max_24h") { datos.insert("Tmax_24h".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("t_min_24h") { datos.insert("Tmin_24h".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("ll_24h") { datos.insert("LL_24h".to_string(), v.clone()); }
                if let Some(v) = hora_data_obj.get("correc_alt") { datos.insert("correc_alt".to_string(), v.clone()); }

                // Synop
                let mut synop = serde_json::Map::new();
                for (key, value) in hora_data_obj.iter() {
                    if key.starts_with("meteo_") || key.starts_with("extra_") {
                        let synop_name = to_synop_name(key);
                        synop.insert(synop_name, value.clone());
                    }
                }

                if !synop.is_empty() { hora_structure.insert("synop".to_string(), Value::Object(synop)); }
                if !datos.is_empty() { hora_structure.insert("datos".to_string(), Value::Object(datos)); }

                // Calculado
                let mut calculado = serde_json::Map::new();
                if let Some(v) = hora_data_obj.get("pres_nmm") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() { calculado.insert("pres_nmm".to_string(), v.clone()); }
                }
                if let Some(v) = hora_data_obj.get("punto_rocio") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() { calculado.insert("pr".to_string(), v.clone()); }
                }
                if let Some(v) = hora_data_obj.get("tension_vapor") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() { calculado.insert("tv".to_string(), v.clone()); }
                }
                if let Some(v) = hora_data_obj.get("humedad_relativa") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() { calculado.insert("hr".to_string(), v.clone()); }
                }
                if let Some(v) = hora_data_obj.get("diferencia") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() { calculado.insert("dif".to_string(), v.clone()); }
                }
                if !calculado.is_empty() { hora_structure.insert("calculado".to_string(), Value::Object(calculado)); }

                let hora_observer = hora_data_obj
                    .get("nombre_observador")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string())
                    .filter(|s| !s.trim().is_empty())
                    .or_else(|| observer_name.clone());

                if let Some(name) = hora_observer {
                    hora_structure.insert("observador".to_string(), Value::String(name));
                }

                horas_map.insert(hora_key.clone(), Value::Object(hora_structure));
            }
        }
    }

    root_map.insert("horas".to_string(), Value::Object(horas_map));

    // Agregar datos de los CLIs si se recibieron del frontend
    if let Some(c3074) = cli3074 {
        if !c3074.is_null() {
            root_map.insert("cli3074".to_string(), c3074);
        }
    }
    if let Some(c4074) = cli4074 {
        if !c4074.is_null() {
            root_map.insert("cli4074".to_string(), c4074);
        }
    }
    if let Some(c5074) = cli5074 {
        if !c5074.is_null() {
            root_map.insert("cli5074".to_string(), c5074);
        }
    }

    let data_str = serde_json::to_string_pretty(&root_map).map_err(|e| e.to_string())?;
    crate::infrastructure::storage::atomic_write(&filepath, &data_str).map_err(|e| e.to_string())?;

    let mut res = HashMap::new();
    res.insert("success".to_string(), "true".to_string());
    res.insert("filepath".to_string(), filepath.to_string_lossy().to_string());
    res.insert("filename".to_string(), filename);
    res.insert("backup_path".to_string(), backup_path);

    Ok(res)
}

#[tauri::command]
pub fn get_observation(
    app_handle: AppHandle,
    station_code: String,
    fecha: String,
) -> Result<Value, String> {
    let base_dir = get_arca_base_dir(&app_handle, crate::infrastructure::storage::SYNOP_MODULE);
    get_observation_core(&base_dir, station_code, fecha)
}

// pub para tests de integración
pub fn get_observation_core(
    base_dir: &Path,
    station_code: String,
    fecha: String,
) -> Result<Value, String> {
    validate_inputs(&station_code, &fecha)?;
    let (year, month) = parse_date_parts(&fecha);
    let fecha_formatted = format_date_for_filename(&fecha);
    let filename = format!("{}{}.json", station_code, fecha_formatted);

    let mut filepath = base_dir.to_path_buf();
    filepath.push(&station_code);
    filepath.push(&year);
    filepath.push(&month);
    filepath.push(&filename);

    if filepath.exists() {
        let data = fs::read_to_string(&filepath).map_err(|e| e.to_string())?;
        let json: Value = serde_json::from_str(&data).map_err(|e| e.to_string())?;

        let mut result = serde_json::Map::new();

        if let Some(json_obj) = json.as_object() {
            // Meta
            if let Some(meta) = json_obj.get("meta") {
                if let Some(meta_obj) = meta.as_object() {
                    if let Some(v) = meta_obj.get("estacion") {
                        result.insert("station_id".to_string(), v.clone());
                    }
                    if let Some(fecha_val) = meta_obj.get("fecha") {
                        let f = fecha_val.as_str().unwrap_or("");
                        if f.len() == 6 {
                            let dd = &f[0..2];
                            let mm = &f[2..4];
                            let aa = &f[4..6];
                            let yyyy = format!("20{}", aa);
                            result.insert(
                                "fecha".to_string(),
                                Value::String(format!("{}-{}-{}", yyyy, mm, dd)),
                            );
                        }
                    }
                    if let Some(v) = meta_obj.get("observador") {
                        result.insert("observador".to_string(), v.clone());
                    }
                }
            }

            // Horas
            if let Some(horas) = json_obj.get("horas") {
                if let Some(horas_obj) = horas.as_object() {
                    for (hora_key, hora_data) in horas_obj.iter() {
                        if let Some(hora_obj) = hora_data.as_object() {
                            let mut flat_hora = serde_json::Map::new();

                            let datos = hora_obj.get("datos").and_then(|d| d.as_object());
                            let synop = hora_obj.get("synop").and_then(|s| s.as_object());
                            let calculado = hora_obj.get("calculado").and_then(|c| c.as_object());

                            // DATOS
                            if let Some(datos_obj) = datos {
                                for (key, value) in datos_obj.iter() {
                                    flat_hora.insert(key.clone(), value.clone());
                                }
                            }

                            // SYNOP
                            if let Some(synop_obj) = synop {
                                for (key, value) in synop_obj.iter() {
                                    let frontend_name = to_frontend_name(key);
                                    flat_hora.insert(frontend_name, value.clone());
                                }
                            }

                            // Sanitizar exclusión mutua de 0CS (meteo_6_2) y 56 (meteo_8_1)
                            let val_6_2 = flat_hora.get("meteo_6_2").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
                            let val_8_1 = flat_hora.get("meteo_8_1").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();

                            let mut final_6_2 = val_6_2.clone();
                            let mut final_8_1 = val_8_1.clone();

                            // Si meteo_6_2 no empieza con '0', no pertenece aquí
                            if !val_6_2.is_empty() && !val_6_2.starts_with('0') {
                                final_6_2 = "".to_string();
                                if val_6_2.starts_with("56") && val_8_1.is_empty() {
                                    final_8_1 = val_6_2.clone();
                                }
                            }
                            
                            // Si meteo_8_1 no empieza con '56', no pertenece aquí
                            if !val_8_1.is_empty() && !val_8_1.starts_with("56") {
                                final_8_1 = "".to_string();
                                if val_8_1.starts_with('0') && final_6_2.is_empty() {
                                    final_6_2 = val_8_1.clone();
                                }
                            }

                            flat_hora.insert("meteo_6_2".to_string(), serde_json::Value::String(final_6_2));
                            flat_hora.insert("meteo_8_1".to_string(), serde_json::Value::String(final_8_1));

                            // CALCULADO
                            if let Some(calculado_obj) = calculado {
                                for (key, value) in calculado_obj.iter() {
                                    let frontend_name = match key.as_str() {
                                        "pr" => "punto_rocio",
                                        "tv" => "tension_vapor",
                                        "hr" => "humedad_relativa",
                                        "dif" => "diferencia",
                                        _ => key.as_str(),
                                    };
                                    flat_hora.insert(frontend_name.to_string(), value.clone());
                                }
                            }

                            // Campos automáticos calculados dinámicamente
                            let pres_est = datos.and_then(|d| d.get("pres_est")).and_then(|v| v.as_str()).unwrap_or("");
                            let p3 = datos.and_then(|d| d.get("p3")).and_then(|v| v.as_str()).unwrap_or("");
                            let irixhv = synop.and_then(|s| s.get("IrIXHVV")).and_then(|v| v.as_str()).unwrap_or("");
                            let seven_ww = synop.and_then(|s| s.get("7wwW1W2")).and_then(|v| v.as_str()).unwrap_or("");
                            let nddff_actual = synop.and_then(|s| s.get("Nddff")).and_then(|v| v.as_str()).unwrap_or("");

                            let prev_hora_key = get_prev_hour(hora_key);
                            let nddff_anterior = horas_obj
                                .get(prev_hora_key)
                                .and_then(|h| h.as_object())
                                .and_then(|h| h.get("synop"))
                                .and_then(|s| s.as_object())
                                .and_then(|s| s.get("Nddff"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");

                            let dif = calc_dif(pres_est, p3);
                            let car = calc_car(pres_est, p3);
                            let visibilidad = get_visibilidad_from_irixhv(irixhv);
                            let tiempo_presente = calc_tiempo_presente(seven_ww, nddff_actual, nddff_anterior);

                            if !dif.is_empty() { flat_hora.insert("tend_dif".to_string(), Value::String(dif)); }
                            if !car.is_empty() { flat_hora.insert("tend_car".to_string(), Value::String(car)); }
                            if !visibilidad.is_empty() { flat_hora.insert("visibilidad".to_string(), Value::String(visibilidad)); }
                            if !tiempo_presente.is_empty() { flat_hora.insert("tiempo_presente".to_string(), Value::String(tiempo_presente)); }

                            // Preservar estación
                            if let Some(st_id) = result.get("station_id") {
                                flat_hora.insert("station_id".to_string(), st_id.clone());
                            }
                            // Inyectar nombre del observador en cada hora
                            let obs_val = hora_obj
                                .get("observador")
                                .cloned()
                                .or_else(|| result.get("observador").cloned());

                            if let Some(v) = obs_val {
                                flat_hora.insert("observador".to_string(), v);
                            }
                            // Preservar correc_alt desde datos
                            if let Some(datos_obj) = datos {
                                if let Some(correc) = datos_obj.get("correc_alt") {
                                    flat_hora.insert("correc_alt".to_string(), correc.clone());
                                }
                            }

                            result.insert(hora_key.clone(), Value::Object(flat_hora));
                        }
                    }
                }
            }
        }

        Ok(Value::Object(result))
    } else {
        Err("Observacion no encontrada".to_string())
    }
}

#[tauri::command]
pub fn get_station_date_range(
    app_handle: AppHandle,
    station_code: String,
) -> Result<HashMap<String, Value>, String> {
    validate_inputs(&station_code, "2026-05-28")?;
    let base_dir = get_arca_base_dir(&app_handle, crate::infrastructure::storage::SYNOP_MODULE);
    let station_dir = base_dir.join(&station_code);

    let mut dates = Vec::new();
    if station_dir.exists() {
        let walker = walkdir::WalkDir::new(&station_dir);
        for entry in walker.into_iter().filter_map(|e| e.ok()) {
            if entry.file_type().is_file()
                && entry.path().extension().is_some_and(|ext| ext == "json")
            {
                let fname = entry
                    .path()
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy();
                if fname.len() >= 8 {
                    let date_str = &fname[fname.len() - 8..];
                    let dd = &date_str[0..2];
                    let mm = &date_str[2..4];
                    let yyyy = &date_str[4..8];
                    dates.push(format!("{}-{}-{}", yyyy, mm, dd));
                }
            }
        }
    }

    dates.sort();

    let oldest = dates.first().map(|s| Value::String(s.clone())).unwrap_or(Value::Null);
    let newest = dates.last().map(|s| Value::String(s.clone())).unwrap_or(Value::Null);

    let mut res = HashMap::new();
    res.insert("station_code".to_string(), Value::String(station_code));
    res.insert("oldest_date".to_string(), oldest);
    res.insert("newest_date".to_string(), newest);
    Ok(res)
}
