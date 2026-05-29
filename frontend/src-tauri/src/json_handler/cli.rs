use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use tauri::AppHandle;
use super::utils::*;
use super::synoptic::*;

// =============================================================================
// CLI 3074 - Observaciones de Superficie
// =============================================================================

#[tauri::command]
pub fn save_cli3074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
    data: Value,
) -> Result<String, String> {
    validate_inputs(&station_id, &date)?;
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("La fecha debe tener formato YYYY-MM-DD".to_string());
    }

    let year = parts[0];
    let month = parts[1];

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let target_dir = ensure_arca_dirs_with_station(&base_dir, &station_id, year, month)?;

    let fecha_formatted = format_date_for_filename(&date);
    let file_name = format!("{}{}.json", station_id, fecha_formatted);
    let file_path = target_dir.join(file_name);

    // Leer archivo existente si existe para no borrar datos de Synop u otros CLIs
    let mut root_map = if file_path.exists() {
        let existing_data = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
        let val: Value = serde_json::from_str(&existing_data).map_err(|e| e.to_string())?;
        val.as_object().cloned().unwrap_or_else(serde_json::Map::new)
    } else {
        let mut map = serde_json::Map::new();
        let mut meta = serde_json::Map::new();
        meta.insert("estacion".to_string(), Value::String(station_id.clone()));
        meta.insert("fecha".to_string(), Value::String(fecha_formatted.clone()));
        map.insert("meta".to_string(), Value::Object(meta));
        map
    };

    // Actualizar fecha de última actualización en meta
    if let Some(meta) = root_map.get_mut("meta").and_then(|m| m.as_object_mut()) {
        meta.insert(
            "ultima_actualizacion".to_string(),
            Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
        );
    }

    root_map.insert("cli3074".to_string(), data);

    let json_string = serde_json::to_string_pretty(&root_map).map_err(|e| e.to_string())?;
    fs::write(&file_path, json_string).map_err(|e| format!("Error escribiendo archivo: {}", e))?;

    Ok(format!("Guardado en: {}", file_path.display()))
}

#[tauri::command]
pub fn load_cli3074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
) -> Result<Value, String> {
    validate_inputs(&station_id, &date)?;
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha inválido".to_string());
    }
    let year = parts[0];
    let month = parts[1];

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let mut file_path = base_dir.clone();
    file_path.push(&station_id);
    file_path.push(year);
    file_path.push(month);

    let fecha_formatted = format_date_for_filename(&date);
    let file_name = format!("{}{}.json", station_id, fecha_formatted);
    file_path.push(file_name);

    if !file_path.exists() {
        return Ok(Value::Null);
    }

    let contents = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
    let root_val: Value = serde_json::from_str(&contents).map_err(|e| e.to_string())?;

    let json_val = if let Some(root_obj) = root_val.as_object() {
        root_obj.get("cli3074").cloned().unwrap_or(Value::Null)
    } else {
        Value::Null
    };

    if json_val.is_null() {
        return Ok(Value::Null);
    }

    // Calcular campos automáticos
    if let Some(json_obj) = json_val.as_object() {
        if let Some(horas) = json_obj.get("horas") {
            if let Some(horas_obj) = horas.as_object() {
                let mut new_horas = serde_json::Map::new();

                for (hora_key, hora_data) in horas_obj.iter() {
                    if let Some(hora_obj) = hora_data.as_object() {
                        let mut new_hora = hora_obj.clone();

                        let pres_est = hora_obj.get("pres_est").and_then(|v| v.as_str()).unwrap_or("");
                        let p3 = hora_obj.get("p3").and_then(|v| v.as_str()).unwrap_or("");

                        let existing_dif = hora_obj.get("tend_dif").and_then(|v| v.as_str()).unwrap_or("");
                        let dif = if !existing_dif.is_empty() {
                            format_dif(existing_dif)
                        } else {
                            calc_dif(pres_est, p3)
                        };
                        if !dif.is_empty() {
                            new_hora.insert("tend_dif".to_string(), Value::String(dif));
                        }

                        let existing_car = hora_obj.get("tend_car").and_then(|v| v.as_str()).unwrap_or("");
                        let car = if existing_car.is_empty() {
                            calc_car(pres_est, p3)
                        } else {
                            existing_car.to_string()
                        };
                        if !car.is_empty() {
                            new_hora.insert("tend_car".to_string(), Value::String(car));
                        }

                        let irixhv = hora_obj.get("meteo_4_irixhvv").and_then(|v| v.as_str()).unwrap_or("");
                        let visibilidad = get_visibilidad_from_irixhv(irixhv);
                        if !visibilidad.is_empty() {
                            new_hora.insert("visibilidad".to_string(), Value::String(visibilidad));
                        }

                        let seven_ww = hora_obj.get("meteo_4_6").and_then(|v| v.as_str()).unwrap_or("");
                        let nddff = hora_obj.get("meteo_4_1").and_then(|v| v.as_str()).unwrap_or("");

                        let prev_hour = match hora_key.as_str() {
                            "1" => None, "2" => Some("1"), "3" => Some("2"), "4" => Some("3"),
                            "5" => Some("4"), "6" => Some("5"), "7" => Some("6"), "8" => Some("7"),
                            "9" => Some("8"), "10" => Some("9"), "11" => Some("10"), "12" => Some("11"),
                            "13" => Some("12"), "14" => Some("13"), "15" => Some("14"), "16" => Some("15"),
                            "17" => Some("16"), "18" => Some("17"), "19" => Some("18"), "20" => Some("19"),
                            "21" => Some("20"), "22" => Some("21"), "23" => Some("22"), "24" => Some("23"),
                            _ => None,
                        };

                        let nddff_prev = if let Some(ph) = prev_hour {
                            horas_obj
                                .get(ph)
                                .and_then(|h| h.as_object())
                                .and_then(|h| h.get("meteo_4_1"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                        } else {
                            ""
                        };

                        let tiempo_presente = calc_tiempo_presente(seven_ww, nddff, nddff_prev);
                        if !tiempo_presente.is_empty() {
                            new_hora.insert("tiempo_presente".to_string(), Value::String(tiempo_presente));
                        }

                        new_horas.insert(hora_key.clone(), Value::Object(new_hora));
                    } else {
                        new_horas.insert(hora_key.clone(), hora_data.clone());
                    }
                }

                let mut result = json_val.as_object().unwrap().clone();
                result.insert("horas".to_string(), Value::Object(new_horas));
                return Ok(Value::Object(result));
            }
        }
    }

    Ok(json_val)
}

// =============================================================================
// CLI 4074 - Nubosidad y Temperatura
// =============================================================================

#[tauri::command]
pub fn save_cli4074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
    data: Value,
) -> Result<HashMap<String, String>, String> {
    validate_inputs(&station_id, &date)?;
    let (year, month) = parse_date_parts(&date);

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let target_dir = ensure_arca_dirs_with_station(&base_dir, &station_id, &year, &month)?;

    let fecha_formatted = format_date_for_filename(&date);
    let file_name = format!("{}{}.json", station_id, fecha_formatted);
    let file_path = target_dir.join(file_name);

    // Leer archivo existente si existe
    let mut root_map = if file_path.exists() {
        let existing_data = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
        let val: Value = serde_json::from_str(&existing_data).map_err(|e| e.to_string())?;
        val.as_object().cloned().unwrap_or_else(serde_json::Map::new)
    } else {
        let mut map = serde_json::Map::new();
        let mut meta = serde_json::Map::new();
        meta.insert("estacion".to_string(), Value::String(station_id.clone()));
        meta.insert("fecha".to_string(), Value::String(fecha_formatted.clone()));
        map.insert("meta".to_string(), Value::Object(meta));
        map
    };

    // Actualizar fecha de última actualización en meta
    if let Some(meta) = root_map.get_mut("meta").and_then(|m| m.as_object_mut()) {
        meta.insert(
            "ultima_actualizacion".to_string(),
            Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
        );
    }

    root_map.insert("cli4074".to_string(), data);

    let json_string = serde_json::to_string_pretty(&root_map).map_err(|e| e.to_string())?;
    fs::write(&file_path, json_string).map_err(|e| e.to_string())?;

    let mut result = HashMap::new();
    result.insert("status".to_string(), "saved".to_string());
    result.insert("path".to_string(), file_path.to_string_lossy().to_string());
    Ok(result)
}

#[tauri::command]
pub fn load_cli4074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
) -> Result<Value, String> {
    validate_inputs(&station_id, &date)?;
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha inválido".to_string());
    }
    let year = parts[0];
    let month = parts[1];

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let mut file_path = base_dir.clone();
    file_path.push(&station_id);
    file_path.push(year);
    file_path.push(month);

    let fecha_formatted = format_date_for_filename(&date);
    let file_name = format!("{}{}.json", station_id, fecha_formatted);
    file_path.push(file_name);

    if !file_path.exists() {
        return Ok(Value::Null);
    }

    let contents = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
    let root_val: Value = serde_json::from_str(&contents).map_err(|e| e.to_string())?;

    let json_val = if let Some(root_obj) = root_val.as_object() {
        root_obj.get("cli4074").cloned().unwrap_or(Value::Null)
    } else {
        Value::Null
    };

    Ok(json_val)
}

// =============================================================================
// CLI 5074 - Observaciones Extremas y Fenómenos
// =============================================================================

#[tauri::command]
pub fn save_cli5074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
    data: Value,
) -> Result<HashMap<String, String>, String> {
    validate_inputs(&station_id, &date)?;
    let (year, month) = parse_date_parts(&date);

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let target_dir = ensure_arca_dirs_with_station(&base_dir, &station_id, &year, &month)?;

    let fecha_formatted = format_date_for_filename(&date);
    let file_name = format!("{}{}.json", station_id, fecha_formatted);
    let file_path = target_dir.join(file_name);

    // Leer archivo existente si existe
    let mut root_map = if file_path.exists() {
        let existing_data = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
        let val: Value = serde_json::from_str(&existing_data).map_err(|e| e.to_string())?;
        val.as_object().cloned().unwrap_or_else(serde_json::Map::new)
    } else {
        let mut map = serde_json::Map::new();
        let mut meta = serde_json::Map::new();
        meta.insert("estacion".to_string(), Value::String(station_id.clone()));
        meta.insert("fecha".to_string(), Value::String(fecha_formatted.clone()));
        map.insert("meta".to_string(), Value::Object(meta));
        map
    };

    // Actualizar fecha de última actualización en meta
    if let Some(meta) = root_map.get_mut("meta").and_then(|m| m.as_object_mut()) {
        meta.insert(
            "ultima_actualizacion".to_string(),
            Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
        );
    }

    root_map.insert("cli5074".to_string(), data);

    let json_string = serde_json::to_string_pretty(&root_map).map_err(|e| e.to_string())?;
    fs::write(&file_path, json_string).map_err(|e| e.to_string())?;

    let mut result = HashMap::new();
    result.insert("status".to_string(), "saved".to_string());
    result.insert("path".to_string(), file_path.to_string_lossy().to_string());
    Ok(result)
}

#[tauri::command]
pub fn load_cli5074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
) -> Result<Value, String> {
    validate_inputs(&station_id, &date)?;
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha invalido".to_string());
    }
    let year = parts[0];
    let month = parts[1];

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let mut file_path = base_dir.clone();
    file_path.push(&station_id);
    file_path.push(year);
    file_path.push(month);

    let fecha_formatted = format_date_for_filename(&date);
    let file_name = format!("{}{}.json", station_id, fecha_formatted);
    file_path.push(file_name);

    if !file_path.exists() {
        return Ok(Value::Null);
    }

    let contents = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
    let root_val: Value = serde_json::from_str(&contents).map_err(|e| e.to_string())?;

    let json_val = if let Some(root_obj) = root_val.as_object() {
        root_obj.get("cli5074").cloned().unwrap_or(Value::Null)
    } else {
        Value::Null
    };

    Ok(json_val)
}
