use crate::db::get_db_path;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tauri::AppHandle;

#[derive(Serialize)]
pub struct AuditLog {
    id: i32,
    action: String,
    station_id: String,
    details: Option<String>,
    user_id: Option<i32>,
    timestamp: String,
}

#[derive(Serialize)]
pub struct CorrectionRequest {
    id: i32,
    station_id: String,
    fecha: String,
    hora: String,
    campo: String,
    valor_actual: String,
    valor_propuesto: String,
    justificacion: String,
    estado: String,
    requester_id: i32,
    created_at: String,
}

#[derive(Deserialize)]
pub struct CorrectionRequestCreate {
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub valor_actual: String,
    pub valor_propuesto: String,
    pub justificacion: String,
}

#[tauri::command]
pub fn get_audit_logs(
    app_handle: AppHandle,
    skip: Option<i32>,
    limit: Option<i32>,
) -> Result<Vec<AuditLog>, String> {
    let s = skip.unwrap_or(0);
    let l = limit.unwrap_or(100);
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut stmt = conn.prepare("SELECT id, action, station_id, details, user_id, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?").map_err(|e| e.to_string())?;

    let logs = stmt
        .query_map([l, s], |row| {
            Ok(AuditLog {
                id: row.get(0)?,
                action: row.get(1)?,
                station_id: row.get(2)?,
                details: row.get(3)?,
                user_id: row.get(4)?,
                timestamp: row.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut res = Vec::new();
    for log in logs {
        if let Ok(l) = log {
            res.push(l);
        }
    }
    Ok(res)
}

#[tauri::command]
pub fn get_correction_requests(
    app_handle: AppHandle,
    skip: Option<i32>,
    limit: Option<i32>,
) -> Result<Vec<CorrectionRequest>, String> {
    let s = skip.unwrap_or(0);
    let l = limit.unwrap_or(100);
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut stmt = conn.prepare("SELECT id, station_id, fecha, hora, campo, valor_actual, valor_propuesto, justificacion, estado, requester_id, created_at FROM correction_requests ORDER BY created_at DESC LIMIT ? OFFSET ?").map_err(|e| e.to_string())?;

    let reqs = stmt
        .query_map([l, s], |row| {
            Ok(CorrectionRequest {
                id: row.get(0)?,
                station_id: row.get(1)?,
                fecha: row.get(2)?,
                hora: row.get(3)?,
                campo: row.get(4)?,
                valor_actual: row.get(5)?,
                valor_propuesto: row.get(6)?,
                justificacion: row.get(7)?,
                estado: row.get(8)?,
                requester_id: row.get(9)?,
                created_at: row.get(10)?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut res = Vec::new();
    for r in reqs {
        if let Ok(c) = r {
            res.push(c);
        }
    }
    Ok(res)
}

#[tauri::command]
pub fn create_correction_request(
    app_handle: AppHandle,
    request: CorrectionRequestCreate,
    current_user_id: Option<i32>,
) -> Result<HashMap<String, String>, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;
    let uid = current_user_id.unwrap_or(1); // default 1 if not provided

    conn.execute(
        "INSERT INTO correction_requests (station_id, fecha, hora, campo, valor_actual, valor_propuesto, justificacion, requester_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (&request.station_id, &request.fecha, &request.hora, &request.campo, &request.valor_actual, &request.valor_propuesto, &request.justificacion, &uid),
    ).map_err(|e| e.to_string())?;

    let mut map = HashMap::new();
    map.insert("success".to_string(), "true".to_string());
    Ok(map)
}
