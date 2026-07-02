use app_lib::adapters::sqlite_audit_repository::SqliteAuditRepository;
use app_lib::audit::{Correction, ErrorMark};
use app_lib::ports::AuditRepository;
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use rusqlite::params;
use std::sync::atomic::{AtomicUsize, Ordering};

static TEST_DB_COUNTER: AtomicUsize = AtomicUsize::new(0);

fn setup_test_db() -> (SqliteAuditRepository, Pool<SqliteConnectionManager>) {
    let n = TEST_DB_COUNTER.fetch_add(1, Ordering::SeqCst);
    let mut path = std::env::temp_dir();
    path.push(format!("arca_audit_integration_test_{}_{}.db", std::process::id(), n));
    let _ = std::fs::remove_file(&path);

    let manager = SqliteConnectionManager::file(&path);
    let pool = Pool::new(manager).unwrap();

    let conn = pool.get().unwrap();
    conn.execute_batch(
        r#"
        PRAGMA foreign_keys = ON;

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

        CREATE INDEX IF NOT EXISTS idx_error_marks_station_fecha ON error_marks(station_id, fecha);
        CREATE INDEX IF NOT EXISTS idx_corrections_station_fecha ON corrections(station_id, fecha);
        CREATE INDEX IF NOT EXISTS idx_summary_logs_station_period ON summary_logs(station_id, year, month);
        "#,
    )
    .unwrap();

    let repo = SqliteAuditRepository::new(pool.clone());
    (repo, pool)
}

fn insert_station(conn: &rusqlite::Connection, id: &str) {
    conn.execute(
        "INSERT INTO stations (id, name, provincia, latitud, longitud, elevacion, ch) VALUES (?, ?, ?, ?, ?, ?, ?)",
        params![id, "Test Station", "Test", 0.0, 0.0, 0.0, 0.0],
    )
    .unwrap();
}

#[test]
fn mark_error_inserts_error_mark() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST001");
    }

    let mark = ErrorMark {
        id: None,
        station_id: "ST001".to_string(),
        fecha: "2024-01-15".to_string(),
        hora: "12".to_string(),
        campo: "temperatura".to_string(),
        tipo_error: "fuera_rango".to_string(),
        nota: Some("valor sospechoso".to_string()),
        marcado_por: "analista".to_string(),
        created_at: None,
    };

    let id = repo.mark_error(&mark).unwrap();
    assert!(id > 0);

    let marks = repo.get_error_marks("ST001", "2024-01-15").unwrap();
    assert_eq!(marks.len(), 1);
    assert_eq!(marks[0].campo, "temperatura");
    assert_eq!(marks[0].tipo_error, "fuera_rango");
    assert_eq!(marks[0].marcado_por, "analista");
}

#[test]
fn mark_error_with_invalid_station_rejected() {
    let (repo, _pool) = setup_test_db();

    let mark = ErrorMark {
        id: None,
        station_id: "NOEXISTE".to_string(),
        fecha: "2024-01-15".to_string(),
        hora: "12".to_string(),
        campo: "temperatura".to_string(),
        tipo_error: "fuera_rango".to_string(),
        nota: None,
        marcado_por: "analista".to_string(),
        created_at: None,
    };

    let result = repo.mark_error(&mark);
    assert!(result.is_err(), "Inserting error mark for non-existent station should fail due to FK constraint");
}

#[test]
fn unmark_error_removes_error_mark() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST002");
    }

    let mark = ErrorMark {
        id: None,
        station_id: "ST002".to_string(),
        fecha: "2024-02-10".to_string(),
        hora: "06".to_string(),
        campo: "humedad".to_string(),
        tipo_error: "inconsistencia".to_string(),
        nota: None,
        marcado_por: "analista".to_string(),
        created_at: None,
    };

    let id = repo.mark_error(&mark).unwrap();
    repo.unmark_error(id).unwrap();

    let marks = repo.get_error_marks("ST002", "2024-02-10").unwrap();
    assert!(marks.is_empty());
}

#[test]
fn unmark_error_nonexistent_is_no_op() {
    let (repo, _pool) = setup_test_db();

    let result = repo.unmark_error(9999);
    assert!(result.is_ok(), "Unmarking a non-existent error should be a no-op");
}

#[test]
fn get_error_report_returns_correct_counts() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST003");
    }

    let mark = ErrorMark {
        id: None,
        station_id: "ST003".to_string(),
        fecha: "2024-03-05".to_string(),
        hora: "00".to_string(),
        campo: "presion".to_string(),
        tipo_error: "error".to_string(),
        nota: None,
        marcado_por: "analista".to_string(),
        created_at: None,
    };
    let error_id = repo.mark_error(&mark).unwrap();

    let correction = Correction {
        id: None,
        station_id: "ST003".to_string(),
        fecha: "2024-03-05".to_string(),
        hora: "00".to_string(),
        campo: "presion".to_string(),
        valor_original: "1013".to_string(),
        valor_corregido: "1014".to_string(),
        justificacion: "ajuste por altura".to_string(),
        corregido_por: "supervisor".to_string(),
        aprobado_por: None,
        estado: "pendiente".to_string(),
        created_at: None,
    };
    repo.propose_correction(&correction).unwrap();

    let report = repo
        .get_error_report(Some("ST003".to_string()), Some("2024".to_string()), Some("03".to_string()))
        .unwrap();
    assert_eq!(report.len(), 1);
    assert_eq!(report[0].error_id, error_id);
    assert_eq!(report[0].station_id, "ST003");
    assert_eq!(report[0].valor_original.as_deref(), Some("1013"));
    assert_eq!(report[0].valor_corregido.as_deref(), Some("1014"));
    assert_eq!(report[0].estado.as_deref(), Some("pendiente"));
}

#[test]
fn get_error_report_empty() {
    let (repo, _pool) = setup_test_db();

    let report = repo.get_error_report(None, None, None).unwrap();
    assert!(report.is_empty());
}

#[test]
fn get_daily_error_counts_aggregates_by_day() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST004");
    }

    for hora in &["00", "06", "12"] {
        let mark = ErrorMark {
            id: None,
            station_id: "ST004".to_string(),
            fecha: "2024-04-10".to_string(),
            hora: hora.to_string(),
            campo: "temp".to_string(),
            tipo_error: "tipo".to_string(),
            nota: None,
            marcado_por: "analista".to_string(),
            created_at: None,
        };
        repo.mark_error(&mark).unwrap();
    }

    let mark_other_day = ErrorMark {
        id: None,
        station_id: "ST004".to_string(),
        fecha: "2024-04-11".to_string(),
        hora: "00".to_string(),
        campo: "temp".to_string(),
        tipo_error: "tipo".to_string(),
        nota: None,
        marcado_por: "analista".to_string(),
        created_at: None,
    };
    repo.mark_error(&mark_other_day).unwrap();

    let counts = repo.get_daily_error_counts("ST004", "2024-04-%").unwrap();
    assert_eq!(counts.get("2024-04-10"), Some(&3));
    assert_eq!(counts.get("2024-04-11"), Some(&1));
}

#[test]
fn get_daily_correction_counts_aggregates_by_day() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST005");
    }

    for hora in &["00", "06"] {
        let correction = Correction {
            id: None,
            station_id: "ST005".to_string(),
            fecha: "2024-05-20".to_string(),
            hora: hora.to_string(),
            campo: "temp".to_string(),
            valor_original: "20".to_string(),
            valor_corregido: "21".to_string(),
            justificacion: "ajuste".to_string(),
            corregido_por: "supervisor".to_string(),
            aprobado_por: Some("admin".to_string()),
            estado: "aprobado".to_string(),
            created_at: None,
        };
        repo.propose_correction(&correction).unwrap();
    }

    let correction_other_day = Correction {
        id: None,
        station_id: "ST005".to_string(),
        fecha: "2024-05-21".to_string(),
        hora: "00".to_string(),
        campo: "temp".to_string(),
        valor_original: "22".to_string(),
        valor_corregido: "23".to_string(),
        justificacion: "ajuste".to_string(),
        corregido_por: "supervisor".to_string(),
        aprobado_por: None,
        estado: "pendiente".to_string(),
        created_at: None,
    };
    repo.propose_correction(&correction_other_day).unwrap();

    let counts = repo.get_daily_correction_counts("ST005", "2024-05-%").unwrap();
    assert_eq!(counts.get("2024-05-20"), Some(&2));
    assert_eq!(counts.get("2024-05-21"), Some(&1));
}

#[test]
fn get_approved_corrections_for_date_filters_by_date() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST006");
    }

    for (hora, campo, valor) in [("00", "temperatura", "25"), ("06", "humedad", "80")] {
        let correction = Correction {
            id: None,
            station_id: "ST006".to_string(),
            fecha: "2024-06-15".to_string(),
            hora: hora.to_string(),
            campo: campo.to_string(),
            valor_original: "x".to_string(),
            valor_corregido: valor.to_string(),
            justificacion: "ajuste".to_string(),
            corregido_por: "supervisor".to_string(),
            aprobado_por: Some("admin".to_string()),
            estado: "aprobado".to_string(),
            created_at: None,
        };
        repo.propose_correction(&correction).unwrap();
    }

    let pending_same_date = Correction {
        id: None,
        station_id: "ST006".to_string(),
        fecha: "2024-06-15".to_string(),
        hora: "12".to_string(),
        campo: "presion".to_string(),
        valor_original: "x".to_string(),
        valor_corregido: "1013".to_string(),
        justificacion: "ajuste".to_string(),
        corregido_por: "supervisor".to_string(),
        aprobado_por: None,
        estado: "pendiente".to_string(),
        created_at: None,
    };
    repo.propose_correction(&pending_same_date).unwrap();

    let approved_other_date = Correction {
        id: None,
        station_id: "ST006".to_string(),
        fecha: "2024-06-16".to_string(),
        hora: "00".to_string(),
        campo: "viento".to_string(),
        valor_original: "x".to_string(),
        valor_corregido: "10".to_string(),
        justificacion: "ajuste".to_string(),
        corregido_por: "supervisor".to_string(),
        aprobado_por: Some("admin".to_string()),
        estado: "aprobado".to_string(),
        created_at: None,
    };
    repo.propose_correction(&approved_other_date).unwrap();

    let approved = repo.get_approved_corrections_for_date("ST006", "2024-06-15").unwrap();
    assert_eq!(approved.len(), 2);
    assert!(approved.iter().any(|(h, c, v)| h == "00" && c == "temperatura" && v == "25"));
    assert!(approved.iter().any(|(h, c, v)| h == "06" && c == "humedad" && v == "80"));
}

#[test]
fn get_person_summary_returns_person_stats() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST007");
    }

    let mark = ErrorMark {
        id: None,
        station_id: "ST007".to_string(),
        fecha: "2024-07-01".to_string(),
        hora: "00".to_string(),
        campo: "viento".to_string(),
        tipo_error: "tipo".to_string(),
        nota: None,
        marcado_por: "alice".to_string(),
        created_at: None,
    };
    repo.mark_error(&mark).unwrap();

    let correction_alice = Correction {
        id: None,
        station_id: "ST007".to_string(),
        fecha: "2024-07-01".to_string(),
        hora: "00".to_string(),
        campo: "viento".to_string(),
        valor_original: "10".to_string(),
        valor_corregido: "12".to_string(),
        justificacion: "ajuste".to_string(),
        corregido_por: "alice".to_string(),
        aprobado_por: Some("bob".to_string()),
        estado: "aprobado".to_string(),
        created_at: None,
    };
    repo.propose_correction(&correction_alice).unwrap();

    let correction_charlie = Correction {
        id: None,
        station_id: "ST007".to_string(),
        fecha: "2024-07-02".to_string(),
        hora: "00".to_string(),
        campo: "temp".to_string(),
        valor_original: "20".to_string(),
        valor_corregido: "21".to_string(),
        justificacion: "ajuste".to_string(),
        corregido_por: "charlie".to_string(),
        aprobado_por: None,
        estado: "pendiente".to_string(),
        created_at: None,
    };
    repo.propose_correction(&correction_charlie).unwrap();

    let summary = repo
        .get_person_summary(Some("ST007".to_string()), Some("2024".to_string()), Some("07".to_string()))
        .unwrap();
    assert_eq!(summary.len(), 2);

    let alice = summary.iter().find(|r| r.persona == "alice").unwrap();
    assert_eq!(alice.errores_marcados, 1);
    assert_eq!(alice.correcciones_propuestas, 1);
    assert_eq!(alice.correcciones_aprobadas, 1);

    let charlie = summary.iter().find(|r| r.persona == "charlie").unwrap();
    assert_eq!(charlie.errores_marcados, 0);
    assert_eq!(charlie.correcciones_propuestas, 1);
    assert_eq!(charlie.correcciones_aprobadas, 0);
}

#[test]
fn get_person_summary_empty() {
    let (repo, _pool) = setup_test_db();

    let summary = repo.get_person_summary(None, None, None).unwrap();
    assert!(summary.is_empty());
}

#[test]
fn propose_correction_inserts_correction() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST008");
    }

    let correction = Correction {
        id: None,
        station_id: "ST008".to_string(),
        fecha: "2024-08-10".to_string(),
        hora: "12".to_string(),
        campo: "temperatura".to_string(),
        valor_original: "25.0".to_string(),
        valor_corregido: "25.5".to_string(),
        justificacion: "revisado contra registro manual".to_string(),
        corregido_por: "supervisor".to_string(),
        aprobado_por: Some("admin".to_string()),
        estado: "aprobado".to_string(),
        created_at: None,
    };

    let id = repo.propose_correction(&correction).unwrap();
    assert!(id > 0);

    let corrections = repo.get_corrections("ST008", "2024-08-10").unwrap();
    assert_eq!(corrections.len(), 1);
    assert_eq!(corrections[0].valor_corregido, "25.5");
    assert_eq!(corrections[0].estado, "aprobado");
}

#[test]
fn export_corrected_json_data_source_returns_approved_corrections() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST009");
    }

    for (hora, campo, valor) in [("00", "temperatura", "25.5"), ("12", "humedad", "78")] {
        let correction = Correction {
            id: None,
            station_id: "ST009".to_string(),
            fecha: "2024-09-01".to_string(),
            hora: hora.to_string(),
            campo: campo.to_string(),
            valor_original: "x".to_string(),
            valor_corregido: valor.to_string(),
            justificacion: "ajuste".to_string(),
            corregido_por: "supervisor".to_string(),
            aprobado_por: Some("admin".to_string()),
            estado: "aprobado".to_string(),
            created_at: None,
        };
        repo.propose_correction(&correction).unwrap();
    }

    let pending = Correction {
        id: None,
        station_id: "ST009".to_string(),
        fecha: "2024-09-01".to_string(),
        hora: "06".to_string(),
        campo: "presion".to_string(),
        valor_original: "x".to_string(),
        valor_corregido: "1013".to_string(),
        justificacion: "ajuste".to_string(),
        corregido_por: "supervisor".to_string(),
        aprobado_por: None,
        estado: "pendiente".to_string(),
        created_at: None,
    };
    repo.propose_correction(&pending).unwrap();

    let approved = repo.get_approved_corrections_for_date("ST009", "2024-09-01").unwrap();
    assert_eq!(approved.len(), 2);
    assert!(approved.iter().any(|(h, c, v)| h == "00" && c == "temperatura" && v == "25.5"));
    assert!(approved.iter().any(|(h, c, v)| h == "12" && c == "humedad" && v == "78"));
}

#[test]
fn browse_stations_returns_station_ids() {
    let (_repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST010");
        insert_station(&conn, "ST011");
    }

    let conn = pool.get().unwrap();
    let mut stmt = conn.prepare("SELECT id FROM stations ORDER BY id").unwrap();
    let ids: Vec<String> = stmt
        .query_map([], |row| row.get(0))
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();

    assert_eq!(ids, vec!["ST010".to_string(), "ST011".to_string()]);
}

#[test]
fn browse_years_returns_distinct_years() {
    let (_repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST012");
        for (year, month) in [(2023, 1), (2024, 1), (2024, 2)] {
            conn.execute(
                "INSERT INTO summary_logs (station_id, year, month, data) VALUES (?, ?, ?, ?)",
                params!["ST012", year, month, "{}"],
            )
            .unwrap();
        }
    }

    let conn = pool.get().unwrap();
    let mut stmt = conn
        .prepare("SELECT DISTINCT year FROM summary_logs WHERE station_id = ? ORDER BY year DESC")
        .unwrap();
    let years: Vec<i32> = stmt
        .query_map(["ST012"], |row| row.get(0))
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();

    assert_eq!(years, vec![2024, 2023]);
}

#[test]
fn browse_months_returns_distinct_months() {
    let (_repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST013");
        for month in [1, 2, 2] {
            conn.execute(
                "INSERT INTO summary_logs (station_id, year, month, data) VALUES (?, ?, ?, ?)",
                params!["ST013", 2024, month, "{}"],
            )
            .unwrap();
        }
    }

    let conn = pool.get().unwrap();
    let mut stmt = conn
        .prepare("SELECT DISTINCT month FROM summary_logs WHERE station_id = ? AND year = ? ORDER BY month")
        .unwrap();
    let months: Vec<i32> = stmt
        .query_map(params!["ST013", 2024], |row| row.get(0))
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();

    assert_eq!(months, vec![1, 2]);
}

#[test]
fn browse_days_returns_distinct_days() {
    let (repo, pool) = setup_test_db();
    {
        let conn = pool.get().unwrap();
        insert_station(&conn, "ST014");
        for (fecha, hora) in [("2024-10-05", "00"), ("2024-10-10", "00"), ("2024-10-10", "06")] {
            let mark = ErrorMark {
                id: None,
                station_id: "ST014".to_string(),
                fecha: fecha.to_string(),
                hora: hora.to_string(),
                campo: "temp".to_string(),
                tipo_error: "tipo".to_string(),
                nota: None,
                marcado_por: "analista".to_string(),
                created_at: None,
            };
            repo.mark_error(&mark).unwrap();
        }
    }

    let conn = pool.get().unwrap();
    let mut stmt = conn
        .prepare(
            "SELECT DISTINCT substr(fecha, 9, 2) as day \
             FROM error_marks \
             WHERE station_id = ? AND fecha LIKE ? \
             ORDER BY day"
        )
        .unwrap();
    let days: Vec<String> = stmt
        .query_map(params!["ST014", "2024-10-%"], |row| row.get(0))
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap();

    assert_eq!(days, vec!["05".to_string(), "10".to_string()]);
}
