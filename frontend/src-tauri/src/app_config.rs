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

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;

    fn setup_db() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            "#,
        )
        .unwrap();
        conn
    }

    fn get_config_logic(conn: &Connection, key: &str) -> Result<Option<String>, String> {
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

    fn set_config_logic(conn: &Connection, key: &str, value: &str) -> Result<(), String> {
        conn.execute(
            "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            params![key, value],
        )
        .map_err(|e| e.to_string())?;
        Ok(())
    }

    #[test]
    fn test_get_app_config_returns_none_for_missing_key() {
        let conn = setup_db();
        let value = get_config_logic(&conn, "missing_key").unwrap();
        assert_eq!(value, None);
    }

    #[test]
    fn test_set_app_config_then_get_app_config_returns_value() {
        let conn = setup_db();
        set_config_logic(&conn, "assigned_station", "ST001").unwrap();

        let value = get_config_logic(&conn, "assigned_station").unwrap();
        assert_eq!(value, Some("ST001".to_string()));
    }

    #[test]
    fn test_overwrite_existing_key_returns_new_value() {
        let conn = setup_db();
        set_config_logic(&conn, "theme", "dark").unwrap();
        set_config_logic(&conn, "theme", "light").unwrap();

        let value = get_config_logic(&conn, "theme").unwrap();
        assert_eq!(value, Some("light".to_string()));
    }
}
