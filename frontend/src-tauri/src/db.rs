use rusqlite::{Connection, Result};
use std::path::PathBuf;
use tauri::AppHandle;
use tauri::Manager;
use bcrypt::{hash, DEFAULT_COST};

pub fn get_db_path(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    path.push("arca_local.db");
    path
}

pub fn init_db(app_handle: &AppHandle) -> Result<()> {
    let db_path = get_db_path(app_handle);
    let conn = Connection::open(&db_path)?;

    // Habilitar modo WAL para mejor concurrencia
    conn.pragma_update(None, "journal_mode", &"wal")?;

    // Crear tabla de usuarios si no existe
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )",
        [],
    )?;

    // Crear tablas si no existen
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            station_id TEXT NOT NULL,
            details TEXT,
            user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;

    conn.execute(
        "CREATE TABLE IF NOT EXISTS summary_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            data TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;

    conn.execute(
        "CREATE TABLE IF NOT EXISTS correction_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            campo TEXT NOT NULL,
            valor_actual TEXT NOT NULL,
            valor_propuesto TEXT NOT NULL,
            justificacion TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            requester_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;

    // Seed default users if users table is empty
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM users",
        [],
        |row| row.get(0),
    )?;

    if count == 0 {
        let default_users = vec![
            ("admin@arca.rd", "admin123", "admin"),
            ("encargado@arca.rd", "encargado123", "encargado"),
            ("observador@arca.rd", "observador123", "observador"),
        ];

        for (email, password, role) in default_users {
            let password_hash = hash(password, DEFAULT_COST)
                .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
            conn.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
                [email, &password_hash, role],
            )?;
        }
    }

    Ok(())
}
