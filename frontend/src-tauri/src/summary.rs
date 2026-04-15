use crate::db::get_db_path;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use tauri::AppHandle;

#[derive(Serialize)]
pub struct MonthlySummary {
    id: i32,
    station_id: String,
    year: i32,
    month: i32,
    data: Value,
    created_at: String,
}

#[derive(Deserialize)]
pub struct MonthlySummaryCreate {
    pub station_id: String,
    pub year: i32,
    pub month: i32,
    pub data: Value,
}

#[tauri::command]
pub fn get_monthly_summaries(
    app_handle: AppHandle,
    skip: Option<i32>,
    limit: Option<i32>,
) -> Result<Vec<MonthlySummary>, String> {
    let s = skip.unwrap_or(0);
    let l = limit.unwrap_or(12);
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    // fetch all and parse json string to Value
    let mut stmt = conn.prepare("SELECT id, station_id, year, month, data, created_at FROM summary_logs ORDER BY year DESC, month DESC LIMIT ? OFFSET ?").map_err(|e| e.to_string())?;

    let summaries = stmt
        .query_map([l, s], |row| {
            let data_str: String = row.get(4)?;
            let data_json: Value = serde_json::from_str(&data_str).unwrap_or(Value::Null);

            Ok(MonthlySummary {
                id: row.get(0)?,
                station_id: row.get(1)?,
                year: row.get(2)?,
                month: row.get(3)?,
                data: data_json,
                created_at: row.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?;

    let mut res = Vec::new();
    for sum in summaries {
        if let Ok(m) = sum {
            res.push(m);
        }
    }
    Ok(res)
}

#[tauri::command]
pub fn create_monthly_summary(
    app_handle: AppHandle,
    summary: MonthlySummaryCreate,
) -> Result<HashMap<String, String>, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let data_str = serde_json::to_string(&summary.data).map_err(|e| e.to_string())?;

    conn.execute(
        "INSERT INTO summary_logs (station_id, year, month, data) VALUES (?, ?, ?, ?)",
        (
            &summary.station_id,
            &summary.year,
            &summary.month,
            &data_str,
        ),
    )
    .map_err(|e| e.to_string())?;

    let mut map = HashMap::new();
    map.insert("success".to_string(), "true".to_string());
    Ok(map)
}
