use rusqlite::{params, Connection};
use tauri::{command, AppHandle};
use crate::db::get_db_path;

#[command]
pub fn get_app_config(app_handle: AppHandle, key: String) -> Result<Option<String>, String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    let mut stmt = conn
        .prepare("SELECT value FROM app_config WHERE key = ?")
        .map_err(|e| e.to_string())?;

    let val = stmt.query_row([key], |row| row.get::<_, String>(0));

    match val {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[command]
pub fn set_app_config(app_handle: AppHandle, key: String, value: String) -> Result<(), String> {
    let db_path = get_db_path(&app_handle);
    let conn = Connection::open(&db_path).map_err(|e| e.to_string())?;

    conn.execute(
        "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        params![key, value],
    )
    .map_err(|e| e.to_string())?;

    Ok(())
}

#[command]
pub fn get_assigned_station(app_handle: AppHandle) -> Result<Option<String>, String> {
    get_app_config(app_handle, "assigned_station".to_string())
}
