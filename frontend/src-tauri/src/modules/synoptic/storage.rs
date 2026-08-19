use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use tauri::AppHandle;

use crate::infrastructure::storage::{
    atomic_write, create_backup, ensure_arca_dirs_with_station, get_arca_base_dir, SYNOP_MODULE,
};
use crate::json_handler::utils::{format_date_for_filename, parse_date_parts, validate_inputs};
use crate::modules::synoptic::calculations::{
    get_prev_hour, recalculate_derived_fields, to_frontend_name, to_synop_name,
};

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
    let base_dir = get_arca_base_dir(&app_handle, SYNOP_MODULE);
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

    let mut root_map = if filepath.exists() {
        let existing_data = fs::read_to_string(&filepath).map_err(|e| e.to_string())?;
        let val: Value = serde_json::from_str(&existing_data).map_err(|e| e.to_string())?;
        val.as_object().cloned().unwrap_or_else(serde_json::Map::new)
    } else {
        serde_json::Map::new()
    };

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

    let mut horas_map = serde_json::Map::new();

    if let Some(horas_obj) = observations.as_object() {
        for (hora_key, hora_data) in horas_obj {
            if let Some(hora_data_obj) = hora_data.as_object() {
                let mut hora_structure = serde_json::Map::new();

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

                let mut synop = serde_json::Map::new();
                for (key, value) in hora_data_obj.iter() {
                    if key.starts_with("meteo_") || key.starts_with("extra_") {
                        let synop_name = to_synop_name(key);
                        synop.insert(synop_name, value.clone());
                    }
                }

                if !synop.is_empty() { hora_structure.insert("synop".to_string(), Value::Object(synop)); }
                if !datos.is_empty() { hora_structure.insert("datos".to_string(), Value::Object(datos)); }

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
    atomic_write(&filepath, &data_str).map_err(|e| e.to_string())?;

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
    let base_dir = get_arca_base_dir(&app_handle, SYNOP_MODULE);
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

            if let Some(horas) = json_obj.get("horas") {
                if let Some(horas_obj) = horas.as_object() {
                    for (hora_key, hora_data) in horas_obj.iter() {
                        if let Some(hora_obj) = hora_data.as_object() {
                            let mut flat_hora = serde_json::Map::new();

                            let datos = hora_obj.get("datos").and_then(|d| d.as_object());
                            let synop = hora_obj.get("synop").and_then(|s| s.as_object());
                            let calculado = hora_obj.get("calculado").and_then(|c| c.as_object());

                            if let Some(datos_obj) = datos {
                                for (key, value) in datos_obj.iter() {
                                    flat_hora.insert(key.clone(), value.clone());
                                }
                            }

                            if let Some(synop_obj) = synop {
                                for (key, value) in synop_obj.iter() {
                                    let frontend_name = to_frontend_name(key);
                                    flat_hora.insert(frontend_name, value.clone());
                                }
                            }

                            let val_6_2 = flat_hora.get("meteo_6_2").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();
                            let val_8_1 = flat_hora.get("meteo_8_1").and_then(|v| v.as_str()).unwrap_or("").trim().to_string();

                            let mut final_6_2 = val_6_2.clone();
                            let mut final_8_1 = val_8_1.clone();

                            if !val_6_2.is_empty() && !val_6_2.starts_with('0') {
                                final_6_2 = "".to_string();
                                if val_6_2.starts_with("56") && val_8_1.is_empty() {
                                    final_8_1 = val_6_2.clone();
                                }
                            }
                            if !val_8_1.is_empty() && !val_8_1.starts_with("56") {
                                final_8_1 = "".to_string();
                                if val_8_1.starts_with('0') && final_6_2.is_empty() {
                                    final_6_2 = val_8_1.clone();
                                }
                            }

                            flat_hora.insert("meteo_6_2".to_string(), Value::String(final_6_2));
                            flat_hora.insert("meteo_8_1".to_string(), Value::String(final_8_1));

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

                            // --- política única de recálculo (SYNOP) ---
                            let ts = datos.and_then(|d| d.get("ts")).and_then(|v| v.as_str());
                            let th = datos.and_then(|d| d.get("th")).and_then(|v| v.as_str());
                            let pres_est = datos.and_then(|d| d.get("pres_est")).and_then(|v| v.as_str());
                            let p3 = datos.and_then(|d| d.get("p3")).and_then(|v| v.as_str());
                            let p24 = datos.and_then(|d| d.get("p24")).and_then(|v| v.as_str());
                            let correc_alt = datos.and_then(|d| d.get("correc_alt")).and_then(|v| v.as_str());
                            let irixhv = synop.and_then(|s| s.get("IrIXHVV")).and_then(|v| v.as_str());
                            let seven_ww = synop.and_then(|s| s.get("7wwW1W2")).and_then(|v| v.as_str());
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

                            let derived = recalculate_derived_fields(
                                None,
                                None,
                                ts,
                                th,
                                pres_est,
                                p3,
                                p24,
                                correc_alt,
                                irixhv,
                                seven_ww,
                                Some(nddff_actual),
                                Some(nddff_anterior),
                            );

                            // En carga sinóptica sin pool solo aplicamos SYNOP derivados;
                            // los psicrométricos se preservan del archivo para compat (test 15.0 vs 14.6).
                            // Ponytail: cuando el mensual/audit necesiten pres_nmm recalculado, llaman con pool.
                            if !derived.tend_dif.is_empty() {
                                flat_hora.insert("tend_dif".to_string(), Value::String(derived.tend_dif));
                            }
                            if !derived.tend_car.is_empty() {
                                flat_hora.insert("tend_car".to_string(), Value::String(derived.tend_car));
                            }
                            if !derived.visibilidad.is_empty() {
                                flat_hora.insert("visibilidad".to_string(), Value::String(derived.visibilidad));
                            }
                            if !derived.tiempo_presente.is_empty() {
                                flat_hora.insert("tiempo_presente".to_string(), Value::String(derived.tiempo_presente));
                            }

                            if let Some(st_id) = result.get("station_id") {
                                flat_hora.insert("station_id".to_string(), st_id.clone());
                            }
                            let obs_val = hora_obj
                                .get("observador")
                                .cloned()
                                .or_else(|| result.get("observador").cloned());

                            if let Some(v) = obs_val {
                                flat_hora.insert("observador".to_string(), v);
                            }
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
    let base_dir = get_arca_base_dir(&app_handle, SYNOP_MODULE);
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
