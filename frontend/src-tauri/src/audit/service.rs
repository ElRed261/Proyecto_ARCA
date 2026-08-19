use crate::infrastructure::error::AppError;
use crate::infrastructure::storage::{arca_base_dir, atomic_write, station_dir, SYNOP_MODULE};
use crate::json_handler::synoptic::get_observation_core;
use crate::ports::AuditRepository;
use crate::audit::{AuditObservationData, ErrorMark};
use tauri::AppHandle;
use std::fs;
use std::path::Path;

pub fn month_name_to_num(name: &str) -> Option<&'static str> {
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

pub fn map_frontend_to_json_datos_field(campo: &str) -> Option<&'static str> {
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

pub fn map_frontend_to_json_calculado_field(campo: &str) -> Option<&'static str> {
    match campo {
        "pres_nmm" => Some("pres_nmm"),
        "punto_rocio" => Some("pr"),
        "tension_vapor" => Some("tv"),
        "humedad_relativa" => Some("hr"),
        "diferencia" => Some("dif"),
        _ => None
    }
}

pub fn load_observation_with_audit(
    pool: &crate::db::DbPool,
    app_handle: &AppHandle,
    station: &str,
    date: &str,
) -> Result<AuditObservationData, AppError> {
    let base_dir = arca_base_dir(app_handle, SYNOP_MODULE);
    load_observation_with_audit_core(pool, &base_dir, station, date)
}

// pub para tests de integración
pub fn load_observation_with_audit_core(
    pool: &crate::db::DbPool,
    base_dir: &Path,
    station: &str,
    date: &str,
) -> Result<AuditObservationData, AppError> {
    let mut observation = get_observation_core(base_dir, station.to_string(), date.to_string())
        .map_err(AppError::Validation)?;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.clone());

    let corrections = repo.get_corrections(station, date)?;
    let mut error_marks = repo.get_error_marks(station, date)?;

    let horas_keys = vec!["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"];
    let mut nuevas_marcas = Vec::new();

    if let Some(obs_obj) = observation.as_object() {
        for hora in &horas_keys {
            if let Some(hora_val) = obs_obj.get(*hora) {
                if let Some(hora_obj) = hora_val.as_object() {
                    let mut tiene_datos = false;
                    for (k, v) in hora_obj {
                        if k != "observador" && k != "station_id" && k != "fecha" && k != "nombre_observador" && !v.is_null() {
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
                                    station_id: station.to_string(),
                                    fecha: date.to_string(),
                                    hora: hora.to_string(),
                                    campo: "observador".to_string(),
                                    tipo_error: tipo_err,
                                    nota: Some(nota_err),
                                    marcado_por: marcado_p,
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
                let irixhv = hora_obj.get("meteo_4_irixhvv").and_then(|v| v.as_str()).map(|s| s.to_string());
                let seven_ww = hora_obj.get("meteo_4_6").and_then(|v| v.as_str()).map(|s| s.to_string());
                let nddff_actual = hora_obj.get("meteo_4_1").and_then(|v| v.as_str()).map(|s| s.to_string());

                // política única — ponytail: una sola función para todos los derivados
                let derived = crate::modules::synoptic::calculations::recalculate_derived_fields(
                    Some(pool),
                    Some(station),
                    ts.as_deref(),
                    th.as_deref(),
                    pres_est.as_deref(),
                    p3.as_deref(),
                    p24.as_deref(),
                    correc_alt.as_deref(),
                    irixhv.as_deref(),
                    seven_ww.as_deref(),
                    nddff_actual.as_deref(),
                    None,
                );

                hora_obj.insert("tension_vapor".to_string(), serde_json::Value::String(derived.tension_vapor));
                hora_obj.insert("humedad_relativa".to_string(), serde_json::Value::String(derived.humedad_relativa));
                hora_obj.insert("punto_rocio".to_string(), serde_json::Value::String(derived.punto_rocio));
                hora_obj.insert("diferencia".to_string(), serde_json::Value::String(derived.diferencia));
                hora_obj.insert("pres_nmm".to_string(), serde_json::Value::String(derived.pres_nmm));
                if !derived.visibilidad.is_empty() {
                    hora_obj.insert("visibilidad".to_string(), serde_json::Value::String(derived.visibilidad));
                }
                if !derived.tend_dif.is_empty() {
                    hora_obj.insert("tend_dif".to_string(), serde_json::Value::String(derived.tend_dif));
                }
                if !derived.tend_car.is_empty() {
                    hora_obj.insert("tend_car".to_string(), serde_json::Value::String(derived.tend_car));
                }
                if !derived.tiempo_presente.is_empty() {
                    hora_obj.insert("tiempo_presente".to_string(), serde_json::Value::String(derived.tiempo_presente));
                }
            }
        }
    }

    Ok(AuditObservationData {
        observation,
        error_marks,
        corrections,
    })
}

pub fn export_corrected_json(
    pool: &crate::db::DbPool,
    app_handle: &AppHandle,
    station_id: &str,
    fecha: &str,
) -> Result<String, AppError> {
    crate::json_handler::utils::validate_inputs(station_id, fecha)
        .map_err(AppError::Validation)?;

    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() != 3 {
        return Err(AppError::Validation("Formato de fecha inválido. Debe ser YYYY-MM-DD".to_string()));
    }
    let year = parts[0];
    let month = parts[1];
    let day = parts[2];
    let filename_date = format!("{}{}{}", day, month, year);

    let base_dir = arca_base_dir(app_handle, SYNOP_MODULE);
    let dir_path = station_dir(&base_dir, station_id, year, month);
    let filename = format!("{}{}.json", station_id, filename_date);
    let original_filepath = dir_path.join(&filename);

    if !original_filepath.exists() {
        return Err(AppError::NotFound(format!("No existe la observación original en {:?}", original_filepath)));
    }

    let existing_data = fs::read_to_string(&original_filepath)?;
    let mut root_val: serde_json::Value = serde_json::from_str(&existing_data)?;

    let repo = crate::adapters::sqlite_audit_repository::SqliteAuditRepository::new(pool.clone());
    let corrections_rows = repo.get_approved_corrections_for_date(station_id, fecha)?;

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

                        // política única
                        let derived = crate::modules::synoptic::calculations::recalculate_derived_fields(
                            Some(pool),
                            Some(station_id),
                            ts.as_deref(),
                            th.as_deref(),
                            pres_est.as_deref(),
                            p3.as_deref(),
                            p24.as_deref(),
                            correc_alt.as_deref(),
                            None,
                            None,
                            None,
                            None,
                        );

                        let mut calculado_obj = serde_json::Map::new();
                        if !derived.pres_nmm.is_empty() { calculado_obj.insert("pres_nmm".to_string(), serde_json::Value::String(derived.pres_nmm)); }
                        if !derived.punto_rocio.is_empty() { calculado_obj.insert("pr".to_string(), serde_json::Value::String(derived.punto_rocio)); }
                        if !derived.tension_vapor.is_empty() { calculado_obj.insert("tv".to_string(), serde_json::Value::String(derived.tension_vapor)); }
                        if !derived.humedad_relativa.is_empty() { calculado_obj.insert("hr".to_string(), serde_json::Value::String(derived.humedad_relativa)); }
                        if !derived.diferencia.is_empty() { calculado_obj.insert("dif".to_string(), serde_json::Value::String(derived.diferencia)); }

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
    
    let data_str = serde_json::to_string_pretty(&root_val).map_err(|e| AppError::Internal(e.to_string()))?;
    atomic_write(&corr_filepath, &data_str)?;
    
    Ok(corr_filepath.to_string_lossy().to_string())
}
