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
pub fn audit_browse_stations(app_handle: AppHandle) -> Result<Vec<StationInfo>, String> {
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
                    stations.push(StationInfo { code: name });
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
    if let Ok(entries) = fs::read_dir(year_dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                let name = entry.file_name().to_string_lossy().to_string();
                if name.len() == 2 && name.chars().all(|c| c.is_ascii_digit()) {
                    months.push(name);
                }
            }
        }
    }
    months.sort();
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
                                horas_registradas = horas.len();
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
