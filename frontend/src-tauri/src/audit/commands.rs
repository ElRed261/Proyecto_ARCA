use crate::infrastructure::error::AppError;
use crate::infrastructure::storage::{arca_base_dir, SYNOP_MODULE};
use crate::ports::AuditRepository;
use crate::audit::{StationInfo, DayInfo, ErrorMark, Correction, AuditObservationData, ErrorReportRow, PersonSummaryRow};
use crate::audit::service;
use tauri::AppHandle;
use std::fs;

#[tauri::command]
pub fn audit_browse_stations(pool: tauri::State<'_, crate::db::DbPool>, app_handle: AppHandle) -> Result<Vec<StationInfo>, AppError> {
    let base_dir = arca_base_dir(&app_handle, SYNOP_MODULE);
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
    let mut station_dir = arca_base_dir(&app_handle, SYNOP_MODULE);
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

#[tauri::command]
pub fn audit_browse_months(
    app_handle: AppHandle,
    station: String,
    year: String,
) -> Result<Vec<String>, AppError> {
    let mut year_dir = arca_base_dir(&app_handle, SYNOP_MODULE);
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
                } else if let Some(num) = service::month_name_to_num(&name) {
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
    let mut month_dir = arca_base_dir(&app_handle, SYNOP_MODULE);
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
                if path.extension().is_some_and(|ext| ext == "json") {
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
    service::load_observation_with_audit(pool.inner(), &app_handle, &station, &date)
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
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
#[allow(clippy::too_many_arguments)]
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
    service::export_corrected_json(pool.inner(), &app_handle, &station_id, &fecha)
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
