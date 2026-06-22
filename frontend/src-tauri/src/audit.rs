use crate::infrastructure::error::AppError;
use crate::json_handler::utils::get_arca_base_dir;
use crate::json_handler::synoptic::get_observation;
use crate::ports::AuditRepository;
use serde::{Deserialize, Serialize};
use std::fs;
use tauri::AppHandle;

#[derive(Serialize)]
pub struct StationInfo {
    pub code: String,
    pub name: String,
}

#[derive(Serialize)]
pub struct DayInfo {
    pub filename: String,
    pub date: String,
    pub observador: String,
    pub horas_registradas: usize,
    pub error_count: i64,
    pub correction_count: i64,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct ErrorMark {
    pub id: Option<i32>,
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub tipo_error: String,
    pub nota: Option<String>,
    pub marcado_por: String,
    pub created_at: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Correction {
    pub id: Option<i32>,
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub valor_original: String,
    pub valor_corregido: String,
    pub justificacion: String,
    pub corregido_por: String,
    pub aprobado_por: Option<String>,
    pub estado: String,
    pub created_at: Option<String>,
}

#[derive(Serialize)]
pub struct AuditObservationData {
    pub observation: serde_json::Value,
    pub error_marks: Vec<ErrorMark>,
    pub corrections: Vec<Correction>,
}

#[derive(Serialize)]
pub struct ErrorReportRow {
    pub error_id: i32,
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub tipo_error: String,
    pub nota: Option<String>,
    pub marcado_por: String,
    pub valor_original: Option<String>,
    pub valor_corregido: Option<String>,
    pub justificacion: Option<String>,
    pub corregido_por: Option<String>,
    pub estado: Option<String>,
    pub created_at: String,
}

#[tauri::command]
pub fn audit_browse_stations(pool: tauri::State<'_, crate::db::DbPool>, app_handle: AppHandle) -> Result<Vec<StationInfo>, AppError> {
    let base_dir = get_arca_base_dir(&app_handle, "synop");
    if !base_dir.exists() {
        return Ok(Vec::new());
    }

    let mut stations = Vec::new();
    if let Ok(entries) = fs::read_dir(base_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.chars().all(|c| c.is_ascii_digit()) {
                    let station_name = crate::calculations::get_station_info(&pool, &name)
                        .map(|info| info.name)
                        .unwrap_or_else(|| "Estación Desconocida".to_string());
                    stations.push(StationInfo { code: name, name: station_name });
                }
            }
        }
    }
    stations.sort_by(|a, b| a.code.cmp(&b.code));
    Ok(stations)
}

#[tauri::command]
pub fn audit_browse_years(app_handle: AppHandle, station: String) -> Result<Vec<String>, AppError> {
    let mut station_dir = get_arca_base_dir(&app_handle, "synop");
    station_dir.push(&station);

    if !station_dir.exists() {
        return Ok(Vec::new());
    }

    let mut years = Vec::new();
    if let Ok(entries) = fs::read_dir(station_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.len() == 4 && name.chars().all(|c| c.is_ascii_digit()) {
                    years.push(name);
                }
            }
        }
    }
    years.sort_by(|a, b| b.cmp(a));
    Ok(years)
}

fn month_name_to_num(name: &str) -> Option<&'static str> {
    match name.to_lowercase().as_str() {
        "enero" | "january" => Some("01"),
        "febrero" | "february" => Some("02"),
        "marzo" | "march" => Some("03"),
        "abril" | "april" => Some("04"),
        "mayo" | "may" => Some("05"),
        "junio" | "june" => Some("06"),
        "julio" | "july" => Some("07"),
        "agosto" | "august" => Some("08"),
        "septiembre" | "september" => Some("09"),
        "octubre" | "october" => Some("10"),
        "noviembre" | "november" => Some("11"),
        "diciembre" | "december" => Some("12"),
        _ => None,
    }
}

#[tauri::command]
pub fn audit_browse_months(
    app_handle: AppHandle,
    station: String,
    year: String,
) -> Result<Vec<String>, AppError> {
    let mut year_dir = get_arca_base_dir(&app_handle, "synop");
    year_dir.push(&station);
    year_dir.push(&year);

    if !year_dir.exists() {
        return Ok(Vec::new());
    }

    let mut months = Vec::new();
    if let Ok(entries) = fs::read_dir(&year_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.len() == 2 && name.chars().all(|c| c.is_ascii_digit()) {
                    months.push(name);
                } else if let Some(num) = month_name_to_num(&name) {
                    let old_path = entry.path();
                    let new_path = year_dir.join(num);
                    if !new_path.exists() {
                        let _ = fs::rename(&old_path, &new_path);
                        months.push(num.to_string());
                    } else {
                        if let Ok(files) = fs::read_dir(&old_path) {
                            for f in files.flatten() {
                                let f_old = f.path();
                                if let Some(fname) = f_old.file_name() {
                                    let f_new = new_path.join(fname);
                                    let _ = fs::rename(&f_old, &f_new);
                                }
                            }
                        }
                        let _ = fs::remove_dir(&old_path);
                    }
                }
            }
        }
    }
    months.sort();
    months.dedup();
    Ok(months)
}

#[tauri::command]
pub fn audit_browse_days(
    pool: tauri::State<'_, crate::db::DbPool>,
    app_handle: AppHandle,
    station: String,
    year: String,
    month: String,
) -> Result<Vec<DayInfo>, AppError> {
    let mut month_dir = get_arca_base_dir(&app_handle, "synop");
    month_dir.push(&station);
    month_dir.push(&year);
    month_dir.push(&month);

    if !month_dir.exists() {
        return Ok(Vec::new());
    }

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());
    let month_prefix = format!("{}-{}-%", year, month);
    let error_counts = repo.get_daily_error_counts(&station, &month_prefix)?;
    let correction_counts = repo.get_daily_correction_counts(&station, &month_prefix)?;

    let mut days = Vec::new();
    if let Ok(entries) = fs::read_dir(month_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
                let path = entry.path();
                if path.extension().map_or(false, |ext| ext == "json") {
                    let filename = entry.file_name().to_string_lossy().to_string();
                    let date_str = if filename.len() >= 8 {
                        let base_fname = path.file_stem().unwrap_or_default().to_string_lossy();
                        if base_fname.len() >= 8 {
                            let len = base_fname.len();
                            let date_part = &base_fname[len - 8..];
                            let dd = &date_part[0..2];
                            let mm = &date_part[2..4];
                            let yyyy = &date_part[4..8];
                            format!("{}-{}-{}", yyyy, mm, dd)
                        } else {
                            format!("{}-{}-01", year, month)
                        }
                    } else {
                        format!("{}-{}-01", year, month)
                    };

                    let mut observador = "Desconocido".to_string();
                    let mut horas_registradas = 0;

                    if let Ok(data) = fs::read_to_string(&path) {
                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&data) {
                            if let Some(meta) = json.get("meta") {
                                if let Some(obs) = meta.get("observador").and_then(|o| o.as_str()) {
                                    observador = obs.to_string();
                                }
                            }
                            if let Some(horas) = json.get("horas").and_then(|h| h.as_object()) {
                                for (_hora_key, hora_val) in horas {
                                    let mut tiene_datos = false;
                                    if let Some(hora_obj) = hora_val.as_object() {
                                        if let Some(datos_obj) = hora_obj.get("datos").and_then(|d| d.as_object()) {
                                            for (k, v) in datos_obj {
                                                if k != "correc_alt" && !v.is_null() {
                                                    if let Some(s) = v.as_str() {
                                                        if !s.trim().is_empty() {
                                                            tiene_datos = true;
                                                            break;
                                                        }
                                                    } else {
                                                        tiene_datos = true;
                                                        break;
                                                    }
                                                }
                                            }
                                        }
                                        if !tiene_datos {
                                            if let Some(synop_obj) = hora_obj.get("synop").and_then(|s| s.as_object()) {
                                                for (_k, v) in synop_obj {
                                                    if !v.is_null() {
                                                        if let Some(s) = v.as_str() {
                                                            if !s.trim().is_empty() {
                                                                 tiene_datos = true;
                                                                 break;
                                                            }
                                                        } else {
                                                            tiene_datos = true;
                                                            break;
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    if tiene_datos {
                                        horas_registradas += 1;
                                    }
                                }
                            }
                        }
                    }

                    let error_count = *error_counts.get(&date_str).unwrap_or(&0);
                    let correction_count = *correction_counts.get(&date_str).unwrap_or(&0);

                    days.push(DayInfo {
                        filename,
                        date: date_str,
                        observador,
                        horas_registradas,
                        error_count,
                        correction_count,
                    });
                }
            }
        }
    }

    days.sort_by(|a, b| a.date.cmp(&b.date));
    Ok(days)
}

#[tauri::command]
pub fn audit_load_observation(
    pool: tauri::State<'_, crate::db::DbPool>,
    app_handle: AppHandle,
    station: String,
    date: String,
) -> Result<AuditObservationData, AppError> {
    let mut observation = get_observation(app_handle.clone(), station.clone(), date.clone())
        .map_err(|e| AppError::Validation(e))?;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());

    let corrections = repo.get_corrections(&station, &date)?;

    let mut error_marks = repo.get_error_marks(&station, &date)?;

    let horas_keys = vec!["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"];
    let mut nuevas_marcas = Vec::new();

    if let Some(obs_obj) = observation.as_object() {
        for hora in &horas_keys {
            if let Some(hora_val) = obs_obj.get(*hora) {
                if let Some(hora_obj) = hora_val.as_object() {
                    let mut tiene_datos = false;
                    for (k, v) in hora_obj {
                        if k != "observador" && k != "station_id" && k != "fecha" && k != "nombre_observador" {
                            if !v.is_null() {
                                if let Some(s) = v.as_str() {
                                    if !s.trim().is_empty() {
                                        tiene_datos = true;
                                        break;
                                    }
                                } else {
                                    tiene_datos = true;
                                    break;
                                }
                            }
                        }
                    }

                    if tiene_datos {
                        let obs_name = hora_obj.get("observador")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .trim();

                        if obs_name.is_empty() || obs_name == "Desconocido" {
                            let ya_marcado = error_marks.iter().any(|m| m.hora == **hora && m.campo == "observador");
                            if !ya_marcado {
                                let tipo_err = "Falta nombre de observador".to_string();
                                let nota_err = "Generado automáticamente: observador no especificado en el turno.".to_string();
                                let marcado_p = "Sistema de Calidad".to_string();

                                let new_mark = ErrorMark {
                                    id: None,
                                    station_id: station.clone(),
                                    fecha: date.clone(),
                                    hora: hora.to_string(),
                                    campo: "observador".to_string(),
                                    tipo_error: tipo_err.clone(),
                                    nota: Some(nota_err.clone()),
                                    marcado_por: marcado_p.clone(),
                                    created_at: Some(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
                                };

                                if let Ok(inserted_id) = repo.mark_error(&new_mark) {
                                    let mut final_mark = new_mark.clone();
                                    final_mark.id = Some(inserted_id);
                                    nuevas_marcas.push(final_mark);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    error_marks.extend(nuevas_marcas);

    if let Some(obs_obj) = observation.as_object_mut() {
        for corr in &corrections {
            if corr.estado == "aprobado" {
                if let Some(hora_val) = obs_obj.get_mut(&corr.hora) {
                    if let Some(hora_obj) = hora_val.as_object_mut() {
                        hora_obj.insert(corr.campo.clone(), serde_json::Value::String(corr.valor_corregido.clone()));
                    }
                }
            }
        }

        for (_hora_key, hora_val) in obs_obj.iter_mut() {
            if let Some(hora_obj) = hora_val.as_object_mut() {
                let ts = hora_obj.get("ts").and_then(|v| v.as_str()).map(|s| s.to_string());
                let th = hora_obj.get("th").and_then(|v| v.as_str()).map(|s| s.to_string());
                let pres_est = hora_obj.get("pres_est").and_then(|v| v.as_str()).map(|s| s.to_string());
                let p3 = hora_obj.get("p3").and_then(|v| v.as_str()).map(|s| s.to_string());
                let p24 = hora_obj.get("p24").and_then(|v| v.as_str()).map(|s| s.to_string());
                let correc_alt = hora_obj.get("correc_alt").and_then(|v| v.as_str()).map(|s| s.to_string());

                let calc_req = crate::calculations::CalculationRequest {
                    station_id: Some(station.clone()),
                    correc_alt,
                    ts,
                    th,
                    pres_est,
                    p3,
                    p24,
                    ir: None,
                    ix: None,
                };

                let calc_res = crate::calculations::realizar_calculos(&pool, calc_req);

                hora_obj.insert("tension_vapor".to_string(), serde_json::Value::String(calc_res.tension_vapor));
                hora_obj.insert("humedad_relativa".to_string(), serde_json::Value::String(calc_res.humedad_relativa));
                hora_obj.insert("punto_rocio".to_string(), serde_json::Value::String(calc_res.punto_rocio));
                hora_obj.insert("diferencia".to_string(), serde_json::Value::String(calc_res.diferencia));
                hora_obj.insert("pres_nmm".to_string(), serde_json::Value::String(calc_res.pres_nmm));
            }
        }
    }

    Ok(AuditObservationData {
        observation,
        error_marks,
        corrections,
    })
}

#[tauri::command]
pub fn audit_mark_error(
    session_store: tauri::State<'_, crate::auth::SessionStore>,
    token: String,
    pool: tauri::State<'_, crate::db::DbPool>,
    _app_handle: AppHandle,
    station_id: String,
    fecha: String,
    hora: String,
    campo: String,
    tipo_error: String,
    nota: Option<String>,
) -> Result<ErrorMark, AppError> {
    let session = crate::auth::require_role(&session_store, &token, &["admin", "control_calidad"])?;
    let marcado_por = session.email;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());

    let mark = ErrorMark {
        id: None,
        station_id,
        fecha,
        hora,
        campo,
        tipo_error,
        nota,
        marcado_por,
        created_at: Some(chrono::Local::now().to_rfc3339()),
    };

    let inserted_id = repo.mark_error(&mark)?;

    let mut final_mark = mark;
    final_mark.id = Some(inserted_id);

    Ok(final_mark)
}

#[tauri::command]
pub fn audit_unmark_error(
    session_store: tauri::State<'_, crate::auth::SessionStore>,
    token: String,
    pool: tauri::State<'_, crate::db::DbPool>,
    _app_handle: AppHandle,
    id: i32,
) -> Result<bool, AppError> {
    crate::auth::require_role(&session_store, &token, &["admin", "control_calidad"])?;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());

    if let Ok((station_id, fecha, hora, campo)) = repo.get_mark_details(id) {
        let _ = repo.delete_corrections_by_mark(&station_id, &fecha, &hora, &campo);
    }

    repo.unmark_error(id)?;

    Ok(true)
}

#[tauri::command]
pub fn audit_update_error_mark_note(
    session_store: tauri::State<'_, crate::auth::SessionStore>,
    token: String,
    pool: tauri::State<'_, crate::db::DbPool>,
    _app_handle: AppHandle,
    id: i32,
    nota: Option<String>,
) -> Result<bool, AppError> {
    crate::auth::require_role(&session_store, &token, &["admin", "control_calidad"])?;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());
    repo.update_mark_note(id, nota)?;

    Ok(true)
}

#[tauri::command]
pub fn audit_propose_correction(
    session_store: tauri::State<'_, crate::auth::SessionStore>,
    token: String,
    pool: tauri::State<'_, crate::db::DbPool>,
    _app_handle: AppHandle,
    station_id: String,
    fecha: String,
    hora: String,
    campo: String,
    valor_original: String,
    valor_corregido: String,
    justificacion: String,
) -> Result<Correction, AppError> {
    let session = crate::auth::require_role(&session_store, &token, &["admin", "control_calidad"])?;
    let corregido_por = session.email;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());

    let corr = Correction {
        id: None,
        station_id: station_id.clone(),
        fecha: fecha.clone(),
        hora: hora.clone(),
        campo: campo.clone(),
        valor_original,
        valor_corregido,
        justificacion,
        corregido_por: corregido_por.clone(),
        aprobado_por: Some(corregido_por.clone()),
        estado: "aprobado".to_string(),
        created_at: Some(chrono::Local::now().to_rfc3339()),
    };

    let inserted_id = repo.propose_correction(&corr)?;
    
    let mut final_corr = corr;
    final_corr.id = Some(inserted_id);

    Ok(final_corr)
}

#[tauri::command]
pub fn audit_get_error_report(
    pool: tauri::State<'_, crate::db::DbPool>,
    _app_handle: AppHandle,
    station_id: Option<String>,
    year: Option<String>,
    month: Option<String>,
) -> Result<Vec<ErrorReportRow>, AppError> {
    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());
    repo.get_error_report(station_id, year, month)
}

fn map_frontend_to_json_datos_field(campo: &str) -> Option<&'static str> {
    match campo {
        "ts" => Some("ts"),
        "th" => Some("th"),
        "pres_est" => Some("pres_est"),
        "p3" => Some("p3"),
        "p24" => Some("p24"),
        "viento_dir" => Some("viento_dir"),
        "viento_vel" => Some("viento_vel"),
        "visibilidad" => Some("visibilidad"),
        "t_max" => Some("Tmax"),
        "t_min" => Some("Tmin"),
        "ll" => Some("LL"),
        "t_max_24h" => Some("Tmax_24h"),
        "t_min_24h" => Some("Tmin_24h"),
        "ll_24h" => Some("LL_24h"),
        "correc_alt" => Some("correc_alt"),
        _ => None
    }
}

fn map_frontend_to_json_calculado_field(campo: &str) -> Option<&'static str> {
    match campo {
        "pres_nmm" => Some("pres_nmm"),
        "punto_rocio" => Some("pr"),
        "tension_vapor" => Some("tv"),
        "humedad_relativa" => Some("hr"),
        "diferencia" => Some("dif"),
        _ => None
    }
}

#[tauri::command]
pub fn audit_export_corrected_json(
    session_store: tauri::State<'_, crate::auth::SessionStore>,
    token: String,
    pool: tauri::State<'_, crate::db::DbPool>,
    app_handle: AppHandle,
    station_id: String,
    fecha: String,
) -> Result<String, AppError> {
    crate::auth::require_role(&session_store, &token, &["admin", "control_calidad"])?;
    crate::json_handler::utils::validate_inputs(&station_id, &fecha)
        .map_err(|e| AppError::Validation(e))?;

    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() != 3 {
        return Err(AppError::Validation("Formato de fecha inválido. Debe ser YYYY-MM-DD".to_string()));
    }
    let year = parts[0];
    let month = parts[1];
    let day = parts[2];
    let filename_date = format!("{}{}{}", day, month, year);

    let base_dir = get_arca_base_dir(&app_handle, "synop");
    let dir_path = base_dir.join(&station_id).join(&year).join(&month);
    let filename = format!("{}{}.json", station_id, filename_date);
    let original_filepath = dir_path.join(&filename);

    if !original_filepath.exists() {
        return Err(AppError::NotFound(format!("No existe la observación original en {:?}", original_filepath)));
    }

    let existing_data = fs::read_to_string(&original_filepath)?;
    let mut root_val: serde_json::Value = serde_json::from_str(&existing_data)?;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());
    let corrections_rows = repo.get_approved_corrections_for_date(&station_id, &fecha)?;

    if let Some(root_obj) = root_val.as_object_mut() {
        if let Some(horas_val) = root_obj.get_mut("horas") {
            if let Some(horas_obj) = horas_val.as_object_mut() {
                for (hora, campo, valor_corregido) in corrections_rows {
                    if let Some(hora_val) = horas_obj.get_mut(&hora) {
                        if let Some(hora_obj) = hora_val.as_object_mut() {
                            if campo == "nombre_observador" || campo == "observador" {
                                hora_obj.insert("observador".to_string(), serde_json::Value::String(valor_corregido));
                            }
                            else if let Some(datos_field) = map_frontend_to_json_datos_field(&campo) {
                                if let Some(datos_val) = hora_obj.get_mut("datos") {
                                    if let Some(datos_obj) = datos_val.as_object_mut() {
                                        datos_obj.insert(datos_field.to_string(), serde_json::Value::String(valor_corregido));
                                    }
                                } else {
                                    let mut datos_obj = serde_json::Map::new();
                                    datos_obj.insert(datos_field.to_string(), serde_json::Value::String(valor_corregido));
                                    hora_obj.insert("datos".to_string(), serde_json::Value::Object(datos_obj));
                                }
                            }
                            else if let Some(calc_field) = map_frontend_to_json_calculado_field(&campo) {
                                if let Some(calc_val) = hora_obj.get_mut("calculado") {
                                    if let Some(calc_obj) = calc_val.as_object_mut() {
                                        calc_obj.insert(calc_field.to_string(), serde_json::Value::String(valor_corregido));
                                    }
                                } else {
                                    let mut calc_obj = serde_json::Map::new();
                                    calc_obj.insert(calc_field.to_string(), serde_json::Value::String(valor_corregido));
                                    hora_obj.insert("calculado".to_string(), serde_json::Value::Object(calc_obj));
                                }
                            }
                            else {
                                let synop_field = crate::json_handler::synoptic::to_synop_name(&campo);
                                if let Some(synop_val) = hora_obj.get_mut("synop") {
                                    if let Some(synop_obj) = synop_val.as_object_mut() {
                                        synop_obj.insert(synop_field, serde_json::Value::String(valor_corregido));
                                    }
                                } else {
                                    let mut synop_obj = serde_json::Map::new();
                                    synop_obj.insert(synop_field, serde_json::Value::String(valor_corregido));
                                    hora_obj.insert("synop".to_string(), serde_json::Value::Object(synop_obj));
                                }
                            }
                        }
                    }
                }

                for (_hora_key, hora_val) in horas_obj.iter_mut() {
                    if let Some(hora_obj) = hora_val.as_object_mut() {
                        let mut ts = None;
                        let mut th = None;
                        let mut pres_est = None;
                        let mut p3 = None;
                        let mut p24 = None;
                        let mut correc_alt = None;

                        if let Some(datos_val) = hora_obj.get("datos") {
                            if let Some(datos_obj) = datos_val.as_object() {
                                ts = datos_obj.get("ts").and_then(|v| v.as_str()).map(|s| s.to_string());
                                th = datos_obj.get("th").and_then(|v| v.as_str()).map(|s| s.to_string());
                                pres_est = datos_obj.get("pres_est").and_then(|v| v.as_str()).map(|s| s.to_string());
                                p3 = datos_obj.get("p3").and_then(|v| v.as_str()).map(|s| s.to_string());
                                p24 = datos_obj.get("p24").and_then(|v| v.as_str()).map(|s| s.to_string());
                                correc_alt = datos_obj.get("correc_alt").and_then(|v| v.as_str()).map(|s| s.to_string());
                            }
                        }

                        let calc_req = crate::calculations::CalculationRequest {
                            station_id: Some(station_id.clone()),
                            correc_alt,
                            ts,
                            th,
                            pres_est,
                            p3,
                            p24,
                            ir: None,
                            ix: None,
                        };

                        let calc_res = crate::calculations::realizar_calculos(&pool, calc_req);
                        
                        let mut calculado_obj = serde_json::Map::new();
                        if !calc_res.pres_nmm.is_empty() { calculado_obj.insert("pres_nmm".to_string(), serde_json::Value::String(calc_res.pres_nmm)); }
                        if !calc_res.punto_rocio.is_empty() { calculado_obj.insert("pr".to_string(), serde_json::Value::String(calc_res.punto_rocio)); }
                        if !calc_res.tension_vapor.is_empty() { calculado_obj.insert("tv".to_string(), serde_json::Value::String(calc_res.tension_vapor)); }
                        if !calc_res.humedad_relativa.is_empty() { calculado_obj.insert("hr".to_string(), serde_json::Value::String(calc_res.humedad_relativa)); }
                        if !calc_res.diferencia.is_empty() { calculado_obj.insert("dif".to_string(), serde_json::Value::String(calc_res.diferencia)); }

                        if !calculado_obj.is_empty() {
                            hora_obj.insert("calculado".to_string(), serde_json::Value::Object(calculado_obj));
                        }
                    }
                }
            }
        }

        if let Some(meta_val) = root_obj.get_mut("meta") {
            if let Some(meta_obj) = meta_val.as_object_mut() {
                meta_obj.insert(
                    "ultima_actualizacion".to_string(),
                    serde_json::Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
                );
            }
        }
    }

    let corr_dir = dir_path.join("correcciones");
    if !corr_dir.exists() {
        fs::create_dir_all(&corr_dir)?;
    }
    
    let corr_filename = format!("{}{}_cor.json", station_id, filename_date);
    let corr_filepath = corr_dir.join(&corr_filename);
    
    let data_str = serde_json::to_string_pretty(&root_val)?;
    fs::write(&corr_filepath, data_str)?;
    
    Ok(corr_filepath.to_string_lossy().to_string())
}

#[derive(Serialize)]
pub struct PersonSummaryRow {
    pub persona: String,
    pub errores_marcados: i64,
    pub correcciones_propuestas: i64,
    pub correcciones_aprobadas: i64,
}

#[tauri::command]
pub fn audit_get_person_summary(
    pool: tauri::State<'_, crate::db::DbPool>,
    _app_handle: AppHandle,
    station_id: Option<String>,
    year: Option<String>,
    month: Option<String>,
) -> Result<Vec<PersonSummaryRow>, AppError> {
    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.inner().clone());
    repo.get_person_summary(station_id, year, month)
}
