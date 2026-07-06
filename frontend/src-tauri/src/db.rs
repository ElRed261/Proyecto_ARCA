use rusqlite::{Result, params};
use std::path::PathBuf;
use tauri::AppHandle;
use tauri::Manager;
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use bcrypt::{hash, DEFAULT_COST};

use rusqlite_migration::{Migrations, M};

pub type DbPool = Pool<SqliteConnectionManager>;

pub fn get_migrations() -> Migrations<'static> {
    Migrations::new(vec![
        M::up(
            r#"
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS stations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provincia TEXT NOT NULL,
                latitud REAL NOT NULL,
                longitud REAL NOT NULL,
                elevacion REAL NOT NULL,
                ch REAL NOT NULL,
                is_active INTEGER DEFAULT 1
            );

            INSERT OR IGNORE INTO stations (id, name, provincia, latitud, longitud, elevacion, ch) VALUES
            ('78451', 'Monte Cristi', 'Monte Cristi', 19.8499, -71.6535, 8.0, 0.5),
            ('MDCY', 'Catey', 'Samaná', 19.267, -69.7337, 4.0, 0.8),
            ('78457', 'Puerto Plata', 'Puerto Plata', 19.7542, -70.5632, 16.0, 1.0),
            ('78482', 'Barahona', 'Barahona', 18.24861, -71.12288, 19.5, 1.2),
            ('78467', 'Sabana de la mar', 'Hato Mayor', 19.0527, -69.3888, 11.0, 1.2),
            ('78464', 'Cabrera', 'María Trinidad Sánchez', 19.6444, -69.9063, 18.0, 1.5),
            ('78486', 'Central', 'Santo Domingo', 18.4734, -69.8705, 14.0, 1.6),
            ('78485', 'Las américas', 'Santo Domingo', 18.4331, -69.6796, 7.0, 2.0),
            ('78479', 'Punta Cana', 'La Altagracia', 18.546, -68.3594, 7.0, 2.0),
            ('78484', 'El Higüero', 'Santo Domingo', 18.57696, -69.98158, 27.0, 3.5),
            ('78466', 'Arroyo Barril', 'Samaná', 19.2005, -69.43144, 49.4, 3.5),
            ('78480', 'Jimaní', 'Independencia', 18.4928, -71.853, 45.0, 4.8),
            ('78473', 'Bayaguana', 'Monte Plata', 18.7422, -69.6308, 53.0, 6.0),
            ('78488', 'La Romana', 'La Romana', 18.4485, -68.9093, 62.0, 8.5),
            ('78460', 'Santiago', 'Santiago', 19.4031, -70.5978, 170.0, 19.8);

            CREATE TABLE IF NOT EXISTS summary_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                data TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (station_id) REFERENCES stations(id)
            );

            CREATE TABLE IF NOT EXISTS error_marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                campo TEXT NOT NULL,
                tipo_error TEXT NOT NULL,
                nota TEXT,
                marcado_por TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (station_id) REFERENCES stations(id)
            );

            CREATE TABLE IF NOT EXISTS corrections (
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
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (station_id) REFERENCES stations(id)
            );

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_error_marks_station_fecha ON error_marks(station_id, fecha);
            CREATE INDEX IF NOT EXISTS idx_corrections_station_fecha ON corrections(station_id, fecha);
            CREATE INDEX IF NOT EXISTS idx_summary_logs_station_period ON summary_logs(station_id, year, month);
            "#
        ),
        M::up(
            r#"
            DROP TABLE IF EXISTS audit_logs;
            DROP TABLE IF EXISTS correction_requests;
            "#
        ),
    ])
}

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

    let mut conn = pool.get()?;

    // Habilitar modo WAL para mejor concurrencia
    conn.pragma_update(None, "journal_mode", "wal")?;
    conn.pragma_update(None, "foreign_keys", "ON")?;

    // Aplicar migraciones
    let migrations = get_migrations();
    migrations.to_latest(&mut conn).map_err(|e| Box::new(e) as Box<dyn std::error::Error>)?;

    // Seed default users if users table is empty
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM users",
        [],
        |row| row.get(0),
    )?;

    if count == 0 {
        use std::fs::File;
        use std::io::Write;

        let mut state = chrono::Utc::now().timestamp_nanos_opt().unwrap_or(123456789) as u64;
        if state == 0 {
            state = 0xDEADC0DE;
        }

        let chars: &[u8] = b"abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";

        let next_char = |s: &mut u64| -> char {
            *s ^= *s << 13;
            *s ^= *s >> 7;
            *s ^= *s << 17;
            let idx = (*s as usize) % chars.len();
            chars[idx] as char
        };

        let make_pass = |s: &mut u64| -> String {
            let mut p = String::new();
            for _ in 0..12 {
                p.push(next_char(s));
            }
            p
        };

        let admin_pass = make_pass(&mut state);
        let encargado_pass = make_pass(&mut state);
        let observador_pass = make_pass(&mut state);
        let calidad_pass = make_pass(&mut state);

        let default_users = vec![
            ("admin@arca.rd", admin_pass.clone(), "admin"),
            ("encargado@arca.rd", encargado_pass.clone(), "encargado"),
            ("observador@arca.rd", observador_pass.clone(), "observador"),
            ("calidad@arca.rd", calidad_pass.clone(), "control_calidad"),
        ];

        for (email, password, role) in &default_users {
            let password_hash = hash(password, DEFAULT_COST)
                .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
            conn.execute(
                "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
                params![email, password_hash, role],
            )?;
        }

        let mut seed_file_path = get_db_path(app_handle);
        seed_file_path.pop(); // Ir al directorio padre (app_data_dir)
        seed_file_path.push("primer_inicio.txt");

        if let Ok(mut file) = File::create(&seed_file_path) {
            let content = format!(
                "=== CREDENCIALES DE PRIMER INICIO PARA PROYECTO ARCA ===\n\n\
                 admin@arca.rd : {}\n\
                 encargado@arca.rd : {}\n\
                 observador@arca.rd : {}\n\
                 calidad@arca.rd : {}\n\n\
                 IMPORTANTE: Por razones de seguridad, cambie estas contraseñas inmediatamente en el panel de administración.\n",
                admin_pass, encargado_pass, observador_pass, calidad_pass
            );
            let _ = file.write_all(content.as_bytes());
            println!("################################################################");
            println!("SE HAN GENERADO LAS CREDENCIALES DE PRIMER INICIO EN:");
            println!("{:?}", seed_file_path);
            println!("################################################################");
        }
    }

    Ok(pool)
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;

    #[test]
    fn test_get_migrations_returns_migrations() {
        let migrations = get_migrations();
        let mut conn = Connection::open_in_memory().unwrap();
        // Applying migrations should succeed, proving the migrations object is valid.
        migrations.to_latest(&mut conn).unwrap();
    }

    #[test]
    fn test_migrations_create_expected_tables() {
        let mut conn = Connection::open_in_memory().unwrap();
        let migrations = get_migrations();
        migrations.to_latest(&mut conn).unwrap();

        let expected_tables = [
            "users",
            "stations",
            "error_marks",
            "corrections",
            "summary_logs",
        ];
        for table in &expected_tables {
            let count: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                    [table],
                    |row| row.get(0),
                )
                .unwrap();
            assert_eq!(count, 1, "Table {} should exist after migrations", table);
        }
    }

    #[test]
    fn test_foreign_keys_pragma_is_on_after_enabling() {
        let mut conn = Connection::open_in_memory().unwrap();
        let migrations = get_migrations();
        migrations.to_latest(&mut conn).unwrap();
        conn.pragma_update(None, "foreign_keys", "ON").unwrap();

        let fk_on: i32 = conn
            .query_row("PRAGMA foreign_keys", [], |row| row.get(0))
            .unwrap();
        assert_eq!(fk_on, 1, "foreign_keys pragma should be ON");
    }

    #[test]
    fn test_foreign_key_enforcement_rejects_invalid_station_id() {
        let mut conn = Connection::open_in_memory().unwrap();
        let migrations = get_migrations();
        migrations.to_latest(&mut conn).unwrap();
        conn.pragma_update(None, "foreign_keys", "ON").unwrap();

        let result = conn.execute(
            "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, marcado_por) VALUES (?, ?, ?, ?, ?, ?)",
            params!["NONEXISTENT", "2024-01-01", "12", "temperatura", "tipo_a", "tester"],
        );
        assert!(result.is_err(), "Inserting error_mark for non-existent station should fail due to FK constraint");
    }

    #[test]
    fn test_expected_indexes_exist() {
        let mut conn = Connection::open_in_memory().unwrap();
        let migrations = get_migrations();
        migrations.to_latest(&mut conn).unwrap();

        let expected_indexes = [
            "idx_corrections_station_fecha",
            "idx_summary_logs_station_period",
        ];
        for idx in &expected_indexes {
            let count: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?",
                    [idx],
                    |row| row.get(0),
                )
                .unwrap();
            assert_eq!(count, 1, "Index {} should exist after migrations", idx);
        }
    }

    #[test]
    fn test_dead_tables_are_dropped_by_migrations() {
        let mut conn = Connection::open_in_memory().unwrap();
        // Simulate an old DB that has the dead tables
        conn.execute_batch(
            "CREATE TABLE audit_logs (id INTEGER); CREATE TABLE correction_requests (id INTEGER);",
        )
        .unwrap();
        // Verify they exist before migrations
        for table in &["audit_logs", "correction_requests"] {
            let count: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                    [table],
                    |row| row.get(0),
                )
                .unwrap();
            assert_eq!(count, 1, "Dead table {} should exist before migrations", table);
        }
        // Run migrations — second migration should drop them
        let migrations = get_migrations();
        migrations.to_latest(&mut conn).unwrap();
        // Verify they are gone
        for table in &["audit_logs", "correction_requests"] {
            let count: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                    [table],
                    |row| row.get(0),
                )
                .unwrap();
            assert_eq!(count, 0, "Dead table {} should be dropped by migrations", table);
        }
    }
}
