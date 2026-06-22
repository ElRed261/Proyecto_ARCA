use crate::db::get_db_path;
use crate::json_handler::utils::get_arca_base_dir;
use crate::json_handler::synoptic::get_observation;
use rusqlite::{Connection, params};
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
    pub date: String, // YYYY-MM-DD
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
pub fn audit_browse_stations(pool: tauri::State<'_, crate::db::DbPool>, app_handle: AppHandle) -> Result<Vec<StationInfo>, String> {
    let base_dir = get_arca_base_dir(&app_handle, "synop");
    if !base_dir.exists() {
        return Ok(Vec::new());
    }

    let mut stations = Vec::new();
    if let Ok(entries) = fs::read_dir(base_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy().to_string();
                // Validar que sea un número de estación (típicamente 5 dígitos)
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
pub fn audit_browse_years(app_handle: AppHandle, station: String) -> Result<Vec<String>, String> {
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
    years.sort_by(|a, b| b.cmp(a)); // Años más recientes primero
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
) -> Result<Vec<String>, String> {
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
    app_handle: AppHandle,
    station: String,
    year: String,
    month: String,
) -> Result<Vec<DayInfo>, String> {
    let mut month_dir = get_arca_base_dir(&app_handle, "synop");
    month_dir.push(&station);
    month_dir.push(&year);
    month_dir.push(&month);

    if !month_dir.exists() {
        return Ok(Vec::new());
    }

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut days = Vec::new();
    if let Ok(entries) = fs::read_dir(month_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
                let path = entry.path();
                if path.extension().map_or(false, |ext| ext == "json") {
                    let filename = entry.file_name().to_string_lossy().to_string();
                    // Extraer fecha
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

                    // Intentar leer para sacar el observador y las horas
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

                    // Consultar errores y correcciones en la BD para este día
                    let error_count: i64 = conn
                        .query_row(
                            "SELECT COUNT(*) FROM error_marks WHERE station_id = ? AND fecha = ?",
                            [&station, &date_str],
                            |row| row.get(0),
                        )
                        .unwrap_or(0);

                    let correction_count: i64 = conn
                        .query_row(
                            "SELECT COUNT(*) FROM corrections WHERE station_id = ? AND fecha = ?",
                            [&station, &date_str],
                            |row| row.get(0),
                        )
                        .unwrap_or(0);

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
) -> Result<AuditObservationData, String> {
    // 1. Cargar la observación aplanada usando la función original
    let mut observation = get_observation(app_handle.clone(), station.clone(), date.clone())?;

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    // 2. Cargar todas las correcciones de la base de datos para esta estación y fecha
    let mut stmt_corr = conn
        .prepare(
            "SELECT id, station_id, fecha, hora, campo, valor_original, valor_corregido, \
             justificacion, corregido_por, aprobado_por, estado, created_at \
             FROM corrections WHERE station_id = ? AND fecha = ?",
        )
        .map_err(|e| e.to_string())?;

    let corrections_iter = stmt_corr
        .query_map([&station, &date], |row| {
            Ok(Correction {
                id: Some(row.get(0)?),
                station_id: row.get(1)?,
                fecha: row.get(2)?,
                hora: row.get(3)?,
                campo: row.get(4)?,
                valor_original: row.get(5)?,
                valor_corregido: row.get(6)?,
                justificacion: row.get(7)?,
                corregido_por: row.get(8)?,
                aprobado_por: row.get(9)?,
                estado: row.get(10)?,
                created_at: Some(row.get(11)?),
            })
        })
        .map_err(|e| e.to_string())?;

    let mut corrections = Vec::new();
    for corr in corrections_iter.flatten() {
        corrections.push(corr);
    }

    // 3. Cargar las marcas de error
    let mut stmt_err = conn
        .prepare(
            "SELECT id, station_id, fecha, hora, campo, tipo_error, nota, marcado_por, created_at \
             FROM error_marks WHERE station_id = ? AND fecha = ?",
        )
        .map_err(|e| e.to_string())?;

    let errors_iter = stmt_err
        .query_map([&station, &date], |row| {
            Ok(ErrorMark {
                id: Some(row.get(0)?),
                station_id: row.get(1)?,
                fecha: row.get(2)?,
                hora: row.get(3)?,
                campo: row.get(4)?,
                tipo_error: row.get(5)?,
                nota: row.get(6)?,
                marcado_por: row.get(7)?,
                created_at: Some(row.get(8)?),
            })
        })
        .map_err(|e| e.to_string())?;

    let mut error_marks = Vec::new();
    for mark in errors_iter.flatten() {
        error_marks.push(mark);
    }

    // 3.1. Validar nombre de observador faltante por hora de manera automática
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

                                let _ = conn.execute(
                                    "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, nota, marcado_por) \
                                     VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    params![
                                        station,
                                        date,
                                        *hora,
                                        "observador",
                                        tipo_err,
                                        nota_err,
                                        marcado_p
                                    ],
                                );

                                if let Ok(last_id) = conn.query_row("SELECT last_insert_rowid()", [], |row| row.get::<_, i32>(0)) {
                                    nuevas_marcas.push(ErrorMark {
                                        id: Some(last_id),
                                        station_id: station.clone(),
                                        fecha: date.clone(),
                                        hora: hora.to_string(),
                                        campo: "observador".to_string(),
                                        tipo_error: tipo_err,
                                        nota: Some(nota_err),
                                        marcado_por: marcado_p,
                                        created_at: Some(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
                                    });
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    error_marks.extend(nuevas_marcas);

    // 4. Superponer correcciones aprobadas sobre la observación aplanada
    if let Some(obs_obj) = observation.as_object_mut() {
        for corr in &corrections {
            if corr.estado == "aprobado" {
                // Las observaciones aplanadas estructuran los datos por hora ("06Z", "12Z", etc.)
                if let Some(hora_val) = obs_obj.get_mut(&corr.hora) {
                    if let Some(hora_obj) = hora_val.as_object_mut() {
                        hora_obj.insert(corr.campo.clone(), serde_json::Value::String(corr.valor_corregido.clone()));
                    }
                }
            }
        }

        // Recalcular campos automáticos/calculados tras aplicar correcciones
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

                // Insertar los nuevos calculados recalculados
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
    app_handle: AppHandle,
    station_id: String,
    fecha: String,
    hora: String,
    campo: String,
    tipo_error: String,
    nota: Option<String>,
    marcado_por: String,
) -> Result<ErrorMark, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    // Evitar marcas duplicadas para el mismo campo/hora/fecha
    let exists: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM error_marks WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
            [&station_id, &fecha, &hora, &campo],
            |row| row.get(0),
        )
        .unwrap_or(0);

    if exists > 0 {
        return Err("Este campo ya está marcado como error".to_string());
    }

    conn.execute(
        "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, nota, marcado_por) \
         VALUES (?, ?, ?, ?, ?, ?, ?)",
        params![station_id, fecha, hora, campo, tipo_error, nota, marcado_por],
    )
    .map_err(|e| e.to_string())?;

    let last_id: i32 = conn
        .query_row("SELECT last_insert_rowid()", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;

    Ok(ErrorMark {
        id: Some(last_id),
        station_id,
        fecha,
        hora,
        campo,
        tipo_error,
        nota,
        marcado_por,
        created_at: Some(chrono::Local::now().to_rfc3339()),
    })
}

#[tauri::command]
pub fn audit_unmark_error(app_handle: AppHandle, id: i32) -> Result<bool, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    // Obtener los detalles de la marca de error antes de borrarla para poder borrar también la corrección propuesta
    let mark_info: Result<(String, String, String, String), _> = conn.query_row(
        "SELECT station_id, fecha, hora, campo FROM error_marks WHERE id = ?",
        [id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
    );

    if let Ok((station_id, fecha, hora, campo)) = mark_info {
        // Borrar correcciones propuestas para este campo
        let _ = conn.execute(
            "DELETE FROM corrections WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
            [station_id, fecha, hora, campo],
        );
    }

    conn.execute("DELETE FROM error_marks WHERE id = ?", [id])
        .map_err(|e| e.to_string())?;

    Ok(true)
}

#[tauri::command]
pub fn audit_update_error_mark_note(
    app_handle: AppHandle,
    id: i32,
    nota: Option<String>,
) -> Result<bool, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    conn.execute("UPDATE error_marks SET nota = ? WHERE id = ?", params![nota, id])
        .map_err(|e| e.to_string())?;

    Ok(true)
}

#[tauri::command]
pub fn audit_propose_correction(
    app_handle: AppHandle,
    station_id: String,
    fecha: String,
    hora: String,
    campo: String,
    valor_original: String,
    valor_corregido: String,
    justificacion: String,
    corregido_por: String,
) -> Result<Correction, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    // Borrar correcciones previas para el mismo campo/hora/fecha
    let _ = conn.execute(
        "DELETE FROM corrections WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
        [&station_id, &fecha, &hora, &campo],
    );

    // Como solo el admin o control_calidad pueden invocar esto (validado en frontend),
    // se aprueba directamente al guardarse
    let estado = "aprobado".to_string();

    conn.execute(
        "INSERT INTO corrections (station_id, fecha, hora, campo, valor_original, valor_corregido, \
         justificacion, corregido_por, aprobado_por, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        params![
            station_id,
            fecha,
            hora,
            campo,
            valor_original,
            valor_corregido,
            justificacion,
            corregido_por,
            Some(corregido_por.clone()),
            estado
        ],
    )
    .map_err(|e| e.to_string())?;

    let last_id: i32 = conn
        .query_row("SELECT last_insert_rowid()", [], |row| row.get(0))
        .map_err(|e| e.to_string())?;

    Ok(Correction {
        id: Some(last_id),
        station_id,
        fecha,
        hora,
        campo,
        valor_original,
        valor_corregido,
        justificacion,
        corregido_por: corregido_por.clone(),
        aprobado_por: Some(corregido_por),
        estado,
        created_at: Some(chrono::Local::now().to_rfc3339()),
    })
}

#[tauri::command]
pub fn audit_get_error_report(
    app_handle: AppHandle,
    station_id: Option<String>,
    year: Option<String>,
    month: Option<String>,
) -> Result<Vec<ErrorReportRow>, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut query = "SELECT e.id, e.station_id, e.fecha, e.hora, e.campo, e.tipo_error, e.nota, e.marcado_por, \
                     c.valor_original, c.valor_corregido, c.justificacion, c.corregido_por, c.estado, e.created_at \
                     FROM error_marks e \
                     LEFT JOIN corrections c ON e.station_id = c.station_id AND e.fecha = c.fecha AND e.hora = c.hora AND e.campo = c.campo \
                     WHERE 1=1".to_string();

    let mut args: Vec<String> = Vec::new();

    if let Some(ref st) = station_id {
        if !st.is_empty() {
            query.push_str(" AND e.station_id = ?");
            args.push(st.clone());
        }
    }

    if let Some(ref y) = year {
        if !y.is_empty() {
            query.push_str(" AND e.fecha LIKE ?");
            args.push(format!("{}-%", y));
        }
    }

    if let Some(ref m) = month {
        if !m.is_empty() {
            // El formato de fecha es YYYY-MM-DD
            if let Some(ref y) = year {
                if !y.is_empty() {
                    // Si ya se especificó año, filtramos por YYYY-MM-%
                    query.pop(); // Sacar el "AND e.fecha LIKE ?" anterior
                    args.pop();
                    query.push_str(" AND e.fecha LIKE ?");
                    args.push(format!("{}-{}-%", y, m));
                } else {
                    query.push_str(" AND e.fecha LIKE ?");
                    args.push(format!("%-{}-%", m));
                }
            } else {
                query.push_str(" AND e.fecha LIKE ?");
                args.push(format!("%-{}-%", m));
            }
        }
    }

    query.push_str(" ORDER BY e.fecha DESC, e.hora ASC");

    let mut stmt = conn.prepare(&query).map_err(|e| e.to_string())?;

    // rusqlite requiere que pasemos los parámetros. Dado que el número de argumentos varía,
    // usamos query_map pasándole una referencia a los parámetros mapeados de rusqlite::params_from_iter.
    let rows_iter = stmt
        .query_map(rusqlite::params_from_iter(args.iter()), |row| {
            Ok(ErrorReportRow {
                error_id: row.get(0)?,
                station_id: row.get(1)?,
                fecha: row.get(2)?,
                hora: row.get(3)?,
                campo: row.get(4)?,
                tipo_error: row.get(5)?,
                nota: row.get(6)?,
                marcado_por: row.get(7)?,
                valor_original: row.get(8)?,
                valor_corregido: row.get(9)?,
                justificacion: row.get(10)?,
                corregido_por: row.get(11)?,
                estado: row.get(12)?,
                created_at: row.get(13)?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut rows = Vec::new();
    for row in rows_iter.flatten() {
        rows.push(row);
    }

    Ok(rows)
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
    pool: tauri::State<'_, crate::db::DbPool>,
    app_handle: AppHandle,
    station_id: String,
    fecha: String, // YYYY-MM-DD
) -> Result<String, String> {
    // 1. Validar y formatear fecha
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha inválido. Debe ser YYYY-MM-DD".to_string());
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
        return Err(format!("No existe la observación original en {:?}", original_filepath));
    }

    // 2. Leer JSON original
    let existing_data = fs::read_to_string(&original_filepath).map_err(|e| e.to_string())?;
    let mut root_val: serde_json::Value = serde_json::from_str(&existing_data).map_err(|e| e.to_string())?;

    // 3. Cargar correcciones aprobadas de la base de datos
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;
    let mut stmt = conn.prepare(
        "SELECT hora, campo, valor_corregido FROM corrections \
         WHERE station_id = ? AND fecha = ? AND estado = 'aprobado'"
    ).map_err(|e| e.to_string())?;
    
    let corrections_rows = stmt.query_map([&station_id, &fecha], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, String>(2)?,
        ))
    }).map_err(|e| e.to_string())?;

    // 4. Aplicar overlay de correcciones
    if let Some(root_obj) = root_val.as_object_mut() {
        if let Some(horas_val) = root_obj.get_mut("horas") {
            if let Some(horas_obj) = horas_val.as_object_mut() {
                for corr_res in corrections_rows {
                    if let Ok((hora, campo, valor_corregido)) = corr_res {
                        if let Some(hora_val) = horas_obj.get_mut(&hora) {
                            if let Some(hora_obj) = hora_val.as_object_mut() {
                                // Observador
                                if campo == "nombre_observador" || campo == "observador" {
                                    hora_obj.insert("observador".to_string(), serde_json::Value::String(valor_corregido));
                                }
                                // Campos instrumentales (datos)
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
                                // Campos calculados
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
                                // Campos SYNOP
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
                }

                // 5. Recalcular las variables derivadas para todas las horas tras aplicar correcciones
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

        // Actualizar ultima_actualizacion en meta
        if let Some(meta_val) = root_obj.get_mut("meta") {
            if let Some(meta_obj) = meta_val.as_object_mut() {
                meta_obj.insert(
                    "ultima_actualizacion".to_string(),
                    serde_json::Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
                );
            }
        }
    }

    // 6. Escribir a subcarpeta correcciones
    let corr_dir = dir_path.join("correcciones");
    if !corr_dir.exists() {
        fs::create_dir_all(&corr_dir).map_err(|e| e.to_string())?;
    }
    
    let corr_filename = format!("{}{}_cor.json", station_id, filename_date);
    let corr_filepath = corr_dir.join(&corr_filename);
    
    let data_str = serde_json::to_string_pretty(&root_val).map_err(|e| e.to_string())?;
    fs::write(&corr_filepath, data_str).map_err(|e| e.to_string())?;
    
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
    app_handle: AppHandle,
    station_id: Option<String>,
    year: Option<String>,
    month: Option<String>,
) -> Result<Vec<PersonSummaryRow>, String> {
    use std::collections::HashMap;

    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut map: HashMap<String, PersonSummaryRow> = HashMap::new();

    // 1. Obtener errores marcados
    let mut err_query = "SELECT marcado_por, COUNT(*) FROM error_marks WHERE 1=1".to_string();
    let mut err_args: Vec<String> = Vec::new();

    if let Some(ref st) = station_id {
        if !st.is_empty() {
            err_query.push_str(" AND station_id = ?");
            err_args.push(st.clone());
        }
    }

    if let Some(ref y) = year {
        if !y.is_empty() {
            err_query.push_str(" AND fecha LIKE ?");
            err_args.push(format!("{}-%", y));
        }
    }

    if let Some(ref m) = month {
        if !m.is_empty() {
            if let Some(ref y) = year {
                if !y.is_empty() {
                    err_query.pop();
                    err_args.pop();
                    err_query.push_str(" AND fecha LIKE ?");
                    err_args.push(format!("{}-{}-%", y, m));
                } else {
                    err_query.push_str(" AND fecha LIKE ?");
                    err_args.push(format!("%-{}-%", m));
                }
            } else {
                err_query.push_str(" AND fecha LIKE ?");
                err_args.push(format!("%-{}-%", m));
            }
        }
    }

    err_query.push_str(" GROUP BY marcado_por");

    let mut err_stmt = conn.prepare(&err_query).map_err(|e| e.to_string())?;
    let err_rows = err_stmt.query_map(rusqlite::params_from_iter(err_args.iter()), |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
    }).map_err(|e| e.to_string())?;

    for r in err_rows.flatten() {
        let (persona, count) = r;
        map.insert(persona.clone(), PersonSummaryRow {
            persona,
            errores_marcados: count,
            correcciones_propuestas: 0,
            correcciones_aprobadas: 0,
        });
    }

    // 2. Obtener correcciones
    let mut corr_query = "SELECT corregido_por, COUNT(*), SUM(CASE WHEN estado = 'aprobado' THEN 1 ELSE 0 END) FROM corrections WHERE 1=1".to_string();
    let mut corr_args: Vec<String> = Vec::new();

    if let Some(ref st) = station_id {
        if !st.is_empty() {
            corr_query.push_str(" AND station_id = ?");
            corr_args.push(st.clone());
        }
    }

    if let Some(ref y) = year {
        if !y.is_empty() {
            corr_query.push_str(" AND fecha LIKE ?");
            corr_args.push(format!("{}-%", y));
        }
    }

    if let Some(ref m) = month {
        if !m.is_empty() {
            if let Some(ref y) = year {
                if !y.is_empty() {
                    corr_query.pop();
                    corr_args.pop();
                    corr_query.push_str(" AND fecha LIKE ?");
                    corr_args.push(format!("{}-{}-%", y, m));
                } else {
                    corr_query.push_str(" AND fecha LIKE ?");
                    corr_args.push(format!("%-{}-%", m));
                }
            } else {
                corr_query.push_str(" AND fecha LIKE ?");
                corr_args.push(format!("%-{}-%", m));
            }
        }
    }

    corr_query.push_str(" GROUP BY corregido_por");

    let mut corr_stmt = conn.prepare(&corr_query).map_err(|e| e.to_string())?;
    let corr_rows = corr_stmt.query_map(rusqlite::params_from_iter(corr_args.iter()), |row| {
        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?, row.get::<_, i64>(2)?))
    }).map_err(|e| e.to_string())?;

    for r in corr_rows.flatten() {
        let (persona, total, aprobadas) = r;
        if let Some(row) = map.get_mut(&persona) {
            row.correcciones_propuestas = total;
            row.correcciones_aprobadas = aprobadas;
        } else {
            map.insert(persona.clone(), PersonSummaryRow {
                persona,
                errores_marcados: 0,
                correcciones_propuestas: total,
                correcciones_aprobadas: aprobadas,
            });
        }
    }

    let mut res: Vec<PersonSummaryRow> = map.into_values().collect();
    res.sort_by(|a, b| b.errores_marcados.cmp(&a.errores_marcados));
    Ok(res)
}

