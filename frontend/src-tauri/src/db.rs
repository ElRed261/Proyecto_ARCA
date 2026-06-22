use rusqlite::{Result, params};
use std::path::PathBuf;
use tauri::AppHandle;
use tauri::Manager;
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use bcrypt::{hash, DEFAULT_COST};

pub type DbPool = Pool<SqliteConnectionManager>;

pub fn get_db_path(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    path.push("arca_local.db");
    path
}

pub fn init_db(app_handle: &AppHandle) -> Result<DbPool, Box<dyn std::error::Error>> {
    let db_path = get_db_path(app_handle);
    let manager = SqliteConnectionManager::file(&db_path);
    let pool = Pool::new(manager)?;

    let conn = pool.get()?;

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

    conn.execute(
        "CREATE TABLE IF NOT EXISTS error_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            campo TEXT NOT NULL,
            tipo_error TEXT NOT NULL,
            nota TEXT,
            marcado_por TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;

    conn.execute(
        "CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            campo TEXT NOT NULL,
            valor_original TEXT NOT NULL,
            valor_corregido TEXT NOT NULL,
            justificacion TEXT NOT NULL,
            corregido_por TEXT NOT NULL,
            aprobado_por TEXT,
            estado TEXT DEFAULT 'pendiente',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;

    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;

    // Seed default users if users table is empty
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM users",
        [],
        |row| row.get(0),
    )?;

    let default_users = vec![
        ("admin@arca.rd", "admin123", "admin"),
        ("encargado@arca.rd", "encargado123", "encargado"),
        ("observador@arca.rd", "observador123", "observador"),
        ("calidad@arca.rd", "calidad123", "control_calidad"),
    ];

    if count == 0 {
        for (email, password, role) in &default_users {
            let password_hash = hash(password, DEFAULT_COST)
                .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
            conn.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
                params![email, password_hash, role],
            )?;
        }
    } else {
        // Asegurar que el usuario de calidad y otros usuarios por defecto existan si la BD ya fue creada previamente
        for (email, password, role) in &default_users {
            let user_exists: i64 = conn.query_row(
                "SELECT COUNT(*) FROM users WHERE email = ?",
                [email],
                |row| row.get(0),
            )?;
            if user_exists == 0 {
                let password_hash = hash(password, DEFAULT_COST)
                    .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
                conn.execute(
                    "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
                    params![email, password_hash, role],
                )?;
            }
        }
    }

    conn.execute(
        "CREATE TABLE IF NOT EXISTS stations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provincia TEXT NOT NULL,
            latitud REAL NOT NULL,
            longitud REAL NOT NULL,
            elevacion REAL NOT NULL,
            ch REAL NOT NULL,
            is_active INTEGER DEFAULT 1
        )",
        [],
    )?;

    // Insertar estaciones por defecto si la tabla está vacía
    let count: i32 = conn.query_row("SELECT COUNT(*) FROM stations", [], |row| row.get(0)).unwrap_or(0);
    if count == 0 {
        let default_stations = vec![
            ("78451", "Monte Cristi", "Monte Cristi", 19.8499, -71.6535, 8.0, 0.5),
            ("MDCY", "Catey", "Samaná", 19.267, -69.7337, 4.0, 0.8),
            ("78457", "Puerto Plata", "Puerto Plata", 19.7542, -70.5632, 16.0, 1.0),
            ("78482", "Barahona", "Barahona", 18.24861, -71.12288, 19.5, 1.2),
            ("78467", "Sabana de la mar", "Hato Mayor", 19.0527, -69.3888, 11.0, 1.2),
            ("78464", "Cabrera", "María Trinidad Sánchez", 19.6444, -69.9063, 18.0, 1.5),
            ("78486", "Central", "Santo Domingo", 18.4734, -69.8705, 14.0, 1.6),
            ("78485", "Las américas", "Santo Domingo", 18.4331, -69.6796, 7.0, 2.0),
            ("78479", "Punta Cana", "La Altagracia", 18.546, -68.3594, 7.0, 2.0),
            ("78484", "El Higüero", "Santo Domingo", 18.57696, -69.98158, 27.0, 3.5),
            ("78466", "Arroyo Barril", "Samaná", 19.2005, -69.43144, 49.4, 3.5),
            ("78480", "Jimaní", "Independencia", 18.4928, -71.853, 45.0, 4.8),
            ("78473", "Bayaguana", "Monte Plata", 18.7422, -69.6308, 53.0, 6.0),
            ("78488", "La Romana", "La Romana", 18.4485, -68.9093, 62.0, 8.5),
            ("78460", "Santiago", "Santiago", 19.4031, -70.5978, 170.0, 19.8),
        ];

        for st in default_stations {
            let _ = conn.execute(
                "INSERT INTO stations (id, name, provincia, latitud, longitud, elevacion, ch) VALUES (?, ?, ?, ?, ?, ?, ?)",
                params![st.0, st.1, st.2, st.3, st.4, st.5, st.6],
            );
        }
    }

    Ok(pool)
}
