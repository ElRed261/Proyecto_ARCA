use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

// =============================================================================
// RUTAS MULTIPLATAFORMA - Documents/OBSERVACIONES/ARCA/{MODULO}/YYYY/MM/
// =============================================================================

/// Obtiene el directorio base de Documents/ARCA/{modulo}/
/// Funciona en Windows, macOS y Linux
fn get_arca_base_dir(app_handle: &AppHandle, modulo: &str) -> PathBuf {
    let mut path = app_handle.path().document_dir().unwrap_or_else(|_| {
        // Fallback para sistemas que no soporten document_dir
        let mut fallback = PathBuf::from(".");
        #[cfg(target_os = "windows")]
        {
            if let Ok(home) = std::env::var("USERPROFILE") {
                fallback = PathBuf::from(home);
            }
        }
        #[cfg(any(target_os = "macos", target_os = "linux"))]
        {
            if let Ok(home) = std::env::var("HOME") {
                fallback = PathBuf::from(home);
                fallback.push("Documents");
            }
        }
        fallback
    });
    path.push("ARCA");
    path.push(modulo);
    path
}

/// Crea la estructura de directorios para un módulo dado
fn ensure_arca_dirs(base_dir: &Path, year: &str, month: &str) -> Result<PathBuf, String> {
    let mut path = base_dir.to_path_buf();
    path.push(year);
    path.push(month);
    fs::create_dir_all(&path).map_err(|e| format!("Error creando directorios: {}", e))?;
    Ok(path)
}

/// Helper para ubicar el directorio principal de datos usando el AppHandle
fn get_base_data_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    path.push("data");
    path
}

fn get_backups_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = get_base_data_dir(app_handle);
    path.push(".backups");
    path
}

/// Extrae DDMMYYYY desde un string "YYYY-MM-DD" o asume DDMMYYYY si no lo es
fn format_date_for_filename(fecha: &str) -> String {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        // YYYY, MM, DD -> DDMMYYYY
        format!("{}{}{}", parts[2], parts[1], parts[0])
    } else {
        fecha.replace("-", "")
    }
}

/// Extrae (year, month) desde un string "YYYY-MM-DD" o DDMMYYYY
fn parse_date_parts(fecha: &str) -> (String, String) {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        (parts[0].to_string(), parts[1].to_string())
    } else if fecha.len() == 8 {
        (fecha[4..8].to_string(), fecha[2..4].to_string())
    } else {
        ("2025".to_string(), "12".to_string())
    }
}

/// Helper para crear un backup manteniendo máximo los últimos 10 de esa estación
fn create_backup(filepath: &Path, station_code: &str, app_handle: &AppHandle) -> Option<String> {
    if !filepath.exists() {
        return None;
    }

    let backup_dir = get_backups_dir(app_handle).join(station_code);
    if !backup_dir.exists() {
        let _ = fs::create_dir_all(&backup_dir);
    }

    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();
    let filename = filepath
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("backup");
    let backup_name = format!("{}.{}.bak", filename, timestamp);
    let backup_path = backup_dir.join(&backup_name);

    if fs::copy(filepath, &backup_path).is_ok() {
        // Clean old backups
        if let Ok(entries) = fs::read_dir(&backup_dir) {
            let mut backups = Vec::new();
            for entry in entries.flatten() {
                if let Ok(metadata) = entry.metadata() {
                    let name = entry.file_name().to_string_lossy().to_string();
                    if name.starts_with(filename) && name.ends_with(".bak") {
                        if let Ok(time) = metadata.modified() {
                            backups.push((time, entry.path()));
                        }
                    }
                }
            }
            backups.sort_by(|a, b| b.0.cmp(&a.0)); // Reverso (nuevos primero)
            for old in backups.iter().skip(10) {
                let _ = fs::remove_file(&old.1);
            }
        }
        return Some(backup_path.to_string_lossy().to_string());
    }

    None
}

// =============================================================================
// COMANDOS DE TAURI
// =============================================================================

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

// Mapeo inverso SYNOP a frontend (para cargar)
const SYNOP_TO_FRONTEND: &[(&str, &str)] = &[
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
    ("9spspsp_1", "meteo_10_2"),
    ("9spspsp_2", "meteo_10_3"),
    ("9spspsp_3", "meteo_10_4"),
    ("9spspsp_4", "meteo_10_5"),
    ("9spspsp_5", "meteo_10_6"),
    ("9spspsp_6", "meteo_12_0"),
    ("9spspsp_7", "meteo_12_1"),
    ("9spspsp_8", "meteo_12_2"),
    ("9spspsp_9", "meteo_12_3"),
    ("9spspsp_10", "meteo_12_4"),
    ("9spspsp_11", "meteo_12_5"),
    ("9spspsp_12", "meteo_12_6"),
    ("9spspsp_13", "meteo_14_0"),
    ("9spspsp_14", "meteo_14_1"),
    ("9spspsp_15", "meteo_14_2"),
    ("9spspsp_16", "meteo_14_3"),
    ("9spspsp_17", "meteo_14_4"),
    ("9spspsp_18", "meteo_14_5"),
    ("9spspsp_19", "meteo_14_6"),
    ("9spspsp_20", "meteo_16_0"),
    ("9spspsp_21", "meteo_16_1"),
    ("9spspsp_22", "meteo_16_2"),
    ("9spspsp_23", "meteo_16_3"),
    ("9spspsp_24", "meteo_16_4"),
];

// Función helper para convertir nombre frontend a SYNOP
fn to_synop_name(frontend_name: &str) -> String {
    for (from, to) in FRONTEND_TO_SYNOP.iter() {
        if *from == frontend_name {
            return to.to_string();
        }
    }
    frontend_name.to_string()
}

// Función helper para convertir nombre SYNOP a frontend
fn to_frontend_name(synop_name: &str) -> String {
    for (from, to) in SYNOP_TO_FRONTEND.iter() {
        if *from == synop_name {
            return to.to_string();
        }
    }
    synop_name.to_string()
}

#[tauri::command]
pub fn save_observation_json(
    app_handle: AppHandle,
    station_code: String,
    fecha: String,
    observations: Value,
    observer_name: Option<String>,
) -> Result<HashMap<String, String>, String> {
    let (year, month) = parse_date_parts(&fecha);

    // Nueva ruta: Documents/ARCA/synoptic/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "synoptic");
    let dir_path = ensure_arca_dirs(&base_dir, &year, &month)?;

    let fecha_formatted = format_date_for_filename(&fecha);
    let filename = format!("{}{}.json", station_code, fecha_formatted);
    let filepath = dir_path.join(&filename);

    let backup_path = create_backup(&filepath, &station_code, &app_handle).unwrap_or_default();

    // Transformar a nueva estructura
    let mut new_structure = serde_json::Map::new();

    // --- META ---
    let mut meta = serde_json::Map::new();
    meta.insert("estacion".to_string(), Value::String(station_code.clone()));
    meta.insert("fecha".to_string(), Value::String(fecha_formatted.clone()));
    if let Some(name) = observer_name {
        meta.insert("observador".to_string(), Value::String(name));
    }
    meta.insert(
        "ultima_actualizacion".to_string(),
        Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
    );
    new_structure.insert("meta".to_string(), Value::Object(meta));

    // --- HORAS ---
    let mut horas_map = serde_json::Map::new();

    if let Some(horas_obj) = observations.as_object() {
        for (hora_key, hora_data) in horas_obj {
            if let Some(hora_data_obj) = hora_data.as_object() {
                let mut hora_structure = serde_json::Map::new();

                // - DATOS: campos que el usuario digita
                let mut datos = serde_json::Map::new();
                // ts, th
                if let Some(v) = hora_data_obj.get("ts") {
                    datos.insert("ts".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("th") {
                    datos.insert("th".to_string(), v.clone());
                }
                // pres_est, p3, p24
                if let Some(v) = hora_data_obj.get("pres_est") {
                    datos.insert("pres_est".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("p3") {
                    datos.insert("p3".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("p24") {
                    datos.insert("p24".to_string(), v.clone());
                }
                // viento
                if let Some(v) = hora_data_obj.get("viento_dir") {
                    datos.insert("viento_dir".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("viento_vel") {
                    datos.insert("viento_vel".to_string(), v.clone());
                }
                // visibilidad
                if let Some(v) = hora_data_obj.get("visibilidad") {
                    datos.insert("visibilidad".to_string(), v.clone());
                }
                // Tmax, Tmin, LL
                if let Some(v) = hora_data_obj.get("t_max") {
                    datos.insert("Tmax".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("t_min") {
                    datos.insert("Tmin".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("ll") {
                    datos.insert("LL".to_string(), v.clone());
                }
                // Tmax_24h, Tmin_24h, LL_24h
                if let Some(v) = hora_data_obj.get("t_max_24h") {
                    datos.insert("Tmax_24h".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("t_min_24h") {
                    datos.insert("Tmin_24h".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("ll_24h") {
                    datos.insert("LL_24h".to_string(), v.clone());
                }
                // campos SYNOP - convertir nombres frontend a nombres SYNOP OMM
                let mut synop = serde_json::Map::new();
                for (key, value) in hora_data_obj.iter() {
                    if key.starts_with("meteo_") || key.starts_with("extra_") {
                        let synop_name = to_synop_name(key);
                        synop.insert(synop_name, value.clone());
                    }
                }
                if !synop.is_empty() {
                    hora_structure.insert("synop".to_string(), Value::Object(synop));
                }
                if !datos.is_empty() {
                    hora_structure.insert("datos".to_string(), Value::Object(datos));
                }

                // - CALCULADO: campos calculados automaticamente
                let mut calculado = serde_json::Map::new();
                if let Some(v) = hora_data_obj.get("pres_nmm") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("pres_nmm".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("punto_rocio") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("pr".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("tension_vapor") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("tv".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("humedad_relativa") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("hr".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("diferencia") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("dif".to_string(), v.clone());
                    }
                }
                if !calculado.is_empty() {
                    hora_structure.insert("calculado".to_string(), Value::Object(calculado));
                }

                horas_map.insert(hora_key.clone(), Value::Object(hora_structure));
            }
        }
    }

    new_structure.insert("horas".to_string(), Value::Object(horas_map));

    let data_str = serde_json::to_string_pretty(&new_structure).map_err(|e| e.to_string())?;
    fs::write(&filepath, data_str).map_err(|e| e.to_string())?;

    let mut res = HashMap::new();
    res.insert("success".to_string(), "true".to_string());
    res.insert(
        "filepath".to_string(),
        filepath.to_string_lossy().to_string(),
    );
    res.insert("filename".to_string(), filename);
    res.insert("backup_path".to_string(), backup_path);

    Ok(res)
}

#[tauri::command]
pub fn get_observations_list(
    app_handle: AppHandle,
    station_code: Option<String>,
) -> Result<HashMap<String, Value>, String> {
    // Nueva ruta: Documents/ARCA/synoptic/
    let base_dir = get_arca_base_dir(&app_handle, "synoptic");

    let mut files = Vec::new();

    let target_dir = if let Some(ref st) = station_code {
        base_dir.join(st)
    } else {
        base_dir.clone()
    };

    if target_dir.exists() {
        let walker = walkdir::WalkDir::new(&target_dir);
        for entry in walker.into_iter().filter_map(|e| e.ok()) {
            if entry.path().is_file() {
                if let Some(ext) = entry.path().extension() {
                    if ext == "json" {
                        if let Ok(rel) = entry.path().strip_prefix(&base_dir) {
                            files.push(Value::String(rel.to_string_lossy().to_string()));
                        }
                    }
                }
            }
        }
    }

    files.sort_by(|a, b| {
        let s1 = a.as_str().unwrap_or("");
        let s2 = b.as_str().unwrap_or("");
        s1.cmp(s2)
    });

    let count = files.len() as i64;
    let mut res = HashMap::new();
    res.insert("files".to_string(), Value::Array(files));
    res.insert(
        "count".to_string(),
        Value::Number(serde_json::Number::from(count)),
    );

    Ok(res)
}

#[tauri::command]
pub fn get_observation(
    app_handle: AppHandle,
    station_code: String,
    fecha: String,
) -> Result<Value, String> {
    let (year, month) = parse_date_parts(&fecha);
    let fecha_formatted = format_date_for_filename(&fecha);
    let filename = format!("{}{}.json", station_code, fecha_formatted);

    // Nueva ruta: Documents/ARCA/synoptic/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "synoptic");
    let mut filepath = base_dir.clone();
    filepath.push(&year);
    filepath.push(&month);
    filepath.push(&filename);

    if filepath.exists() {
        let data = fs::read_to_string(&filepath).map_err(|e| e.to_string())?;
        let json: Value = serde_json::from_str(&data).map_err(|e| e.to_string())?;

        // Transformar nueva estructura al formato del frontend (flattened)
        // Se OMITEN los campos en "calculado" - se recalculan automaticamente
        let mut result = serde_json::Map::new();

        if let Some(json_obj) = json.as_object() {
            // Incluir meta
            if let Some(meta) = json_obj.get("meta") {
                if let Some(meta_obj) = meta.as_object() {
                    if let Some(v) = meta_obj.get("estacion") {
                        result.insert("station_id".to_string(), v.clone());
                    }
                    if let Some(fecha_val) = meta_obj.get("fecha") {
                        // Convertir DDMMAA a YYYY-MM-DD
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

            // Procesar horas
            if let Some(horas) = json_obj.get("horas") {
                if let Some(horas_obj) = horas.as_object() {
                    for (hora_key, hora_data) in horas_obj.iter() {
                        if let Some(hora_obj) = hora_data.as_object() {
                            let mut flat_hora = serde_json::Map::new();

                            // DATOS → misma estrutura flattened
                            if let Some(datos) = hora_obj.get("datos") {
                                if let Some(datos_obj) = datos.as_object() {
                                    for (key, value) in datos_obj.iter() {
                                        flat_hora.insert(key.clone(), value.clone());
                                    }
                                }
                            }

                            // SYNOP → convertir nombres SYNOP a nombres frontend
                            if let Some(synop) = hora_obj.get("synop") {
                                if let Some(synop_obj) = synop.as_object() {
                                    for (key, value) in synop_obj.iter() {
                                        let frontend_name = to_frontend_name(key);
                                        flat_hora.insert(frontend_name, value.clone());
                                    }
                                }
                            }

                            // CALCULADO → SE OMITE! Se recalcula automaticamente
                            // Solo preservamos estacion y correc_alt si existen
                            if let Some(st_id) = result.get("station_id") {
                                flat_hora.insert("station_id".to_string(), st_id.clone());
                            }
                            if let Some(correc) = result.get("correc_alt") {
                                flat_hora.insert("correc_alt".to_string(), correc.clone());
                            }

                            // Agregar al resultado
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
    let station_dir = get_base_data_dir(&app_handle).join(&station_code);

    let mut dates = Vec::new();
    if station_dir.exists() {
        let walker = walkdir::WalkDir::new(&station_dir);
        for entry in walker.into_iter().filter_map(|e| e.ok()) {
            if entry.file_type().is_file()
                && entry.path().extension().map_or(false, |ext| ext == "json")
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

    let oldest = dates
        .first()
        .map(|s| Value::String(s.clone()))
        .unwrap_or(Value::Null);
    let newest = dates
        .last()
        .map(|s| Value::String(s.clone()))
        .unwrap_or(Value::Null);
    let has_data = !dates.is_empty();

    let mut res = HashMap::new();
    res.insert("station_code".to_string(), Value::String(station_code));
    res.insert("oldest_date".to_string(), oldest);
    res.insert("newest_date".to_string(), newest);
    Ok(res)
}

#[tauri::command]
pub fn save_cli3074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
    data: Value,
) -> Result<String, String> {
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("La fecha debe tener formato YYYY-MM-DD".to_string());
    }

    let year = parts[0];
    let month = parts[1];

    // Nueva ruta: Documents/ARCA/cli3074/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "cli3074");
    let target_dir = ensure_arca_dirs(&base_dir, year, month)?;

    let file_name = format!("{}_{}_{}.json", station_id, date, "cli3074");
    let mut file_path = target_dir;
    file_path.push(file_name);

    let json_string = serde_json::to_string_pretty(&data).map_err(|e| e.to_string())?;

    fs::write(&file_path, json_string).map_err(|e| format!("Error escribiendo archivo: {}", e))?;

    Ok(format!("Guardado en: {}", file_path.display()))
}

#[tauri::command]
pub fn load_cli3074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
) -> Result<Value, String> {
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha inválido".to_string());
    }
    let year = parts[0];
    let month = parts[1];

    // Nueva ruta: Documents/ARCA/cli3074/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "cli3074");
    let mut file_path = base_dir.clone();
    file_path.push(year);
    file_path.push(month);

    let file_name = format!("{}_{}_{}.json", station_id, date, "cli3074");
    file_path.push(file_name);

    if !file_path.exists() {
        return Ok(Value::Null);
    }

    let contents = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
    let json_val: Value = serde_json::from_str(&contents).map_err(|e| e.to_string())?;

    Ok(json_val)
}
