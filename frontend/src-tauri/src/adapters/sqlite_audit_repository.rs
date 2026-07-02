use crate::ports::AuditRepository;
use crate::infrastructure::error::AppError;
use crate::audit::{ErrorMark, Correction, ErrorReportRow, PersonSummaryRow};
use rusqlite::params;
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use std::collections::HashMap;

pub struct SqliteAuditRepository {
    pool: Pool<SqliteConnectionManager>,
}

impl SqliteAuditRepository {
    pub fn new(pool: Pool<SqliteConnectionManager>) -> Self {
        SqliteAuditRepository { pool }
    }
}

impl AuditRepository for SqliteAuditRepository {
    fn get_error_marks(&self, station_id: &str, fecha: &str) -> Result<Vec<ErrorMark>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let mut stmt = conn.prepare(
            "SELECT id, station_id, fecha, hora, campo, tipo_error, nota, marcado_por, created_at \
             FROM error_marks WHERE station_id = ? AND fecha = ?"
        )?;

        let rows = stmt.query_map([station_id, fecha], |row| {
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
        })?;

        let mut error_marks = Vec::new();
        for row in rows {
            error_marks.push(row?);
        }
        Ok(error_marks)
    }

    fn get_corrections(&self, station_id: &str, fecha: &str) -> Result<Vec<Correction>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let mut stmt = conn.prepare(
            "SELECT id, station_id, fecha, hora, campo, valor_original, valor_corregido, \
             justificacion, corregido_por, aprobado_por, estado, created_at \
             FROM corrections WHERE station_id = ? AND fecha = ?"
        )?;

        let rows = stmt.query_map([station_id, fecha], |row| {
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
        })?;

        let mut corrections = Vec::new();
        for row in rows {
            corrections.push(row?);
        }
        Ok(corrections)
    }

    fn mark_error(&self, mark: &ErrorMark) -> Result<i32, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        
        let exists: i64 = conn.query_row(
            "SELECT COUNT(*) FROM error_marks WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
            [&mark.station_id, &mark.fecha, &mark.hora, &mark.campo],
            |row| row.get(0),
        )?;

        if exists > 0 {
            return Err(AppError::Validation("Este campo ya está marcado como error".to_string()));
        }

        conn.execute(
            "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, nota, marcado_por) \
             VALUES (?, ?, ?, ?, ?, ?, ?)",
            params![mark.station_id, mark.fecha, mark.hora, mark.campo, mark.tipo_error, mark.nota, mark.marcado_por],
        )?;

        let last_id: i32 = conn.query_row("SELECT last_insert_rowid()", [], |row| row.get(0))?;
        Ok(last_id)
    }

    fn unmark_error(&self, id: i32) -> Result<(), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        conn.execute("DELETE FROM error_marks WHERE id = ?", [id])?;
        Ok(())
    }

    fn get_mark_details(&self, id: i32) -> Result<(String, String, String, String), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let info = conn.query_row(
            "SELECT station_id, fecha, hora, campo FROM error_marks WHERE id = ?",
            [id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        )?;
        Ok(info)
    }

    fn delete_corrections_by_mark(&self, station_id: &str, fecha: &str, hora: &str, campo: &str) -> Result<(), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        conn.execute(
            "DELETE FROM corrections WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
            [station_id, fecha, hora, campo],
        )?;
        Ok(())
    }

    fn update_mark_note(&self, id: i32, note: Option<String>) -> Result<(), AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        conn.execute("UPDATE error_marks SET nota = ? WHERE id = ?", params![note, id])?;
        Ok(())
    }

    fn propose_correction(&self, corr: &Correction) -> Result<i32, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        
        conn.execute(
            "DELETE FROM corrections WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
            [&corr.station_id, &corr.fecha, &corr.hora, &corr.campo],
        )?;

        conn.execute(
            "INSERT INTO corrections (station_id, fecha, hora, campo, valor_original, valor_corregido, \
             justificacion, corregido_por, aprobado_por, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params![
                corr.station_id,
                corr.fecha,
                corr.hora,
                corr.campo,
                corr.valor_original,
                corr.valor_corregido,
                corr.justificacion,
                corr.corregido_por,
                corr.aprobado_por,
                corr.estado
            ],
        )?;

        let last_id: i32 = conn.query_row("SELECT last_insert_rowid()", [], |row| row.get(0))?;
        Ok(last_id)
    }

    fn get_error_report(&self, station_id: Option<String>, year: Option<String>, month: Option<String>) -> Result<Vec<ErrorReportRow>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
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

        let y = year.as_deref().unwrap_or("");
        let m = month.as_deref().unwrap_or("");

        if !y.is_empty() && !m.is_empty() {
            query.push_str(" AND e.fecha LIKE ?");
            args.push(format!("{}-{}-%", y, m));
        } else if !y.is_empty() {
            query.push_str(" AND e.fecha LIKE ?");
            args.push(format!("{}-%", y));
        } else if !m.is_empty() {
            query.push_str(" AND e.fecha LIKE ?");
            args.push(format!("%-{}-%", m));
        }

        query.push_str(" ORDER BY e.fecha DESC, e.hora ASC");

        let mut stmt = conn.prepare(&query)?;
        let rows_iter = stmt.query_map(rusqlite::params_from_iter(args.iter()), |row| {
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
        })?;

        let mut rows = Vec::new();
        for row in rows_iter {
            rows.push(row?);
        }
        Ok(rows)
    }

    fn get_daily_error_counts(&self, station_id: &str, month_prefix: &str) -> Result<HashMap<String, i64>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let mut stmt = conn.prepare(
            "SELECT fecha, COUNT(*) FROM error_marks WHERE station_id = ? AND fecha LIKE ? GROUP BY fecha"
        )?;
        let rows = stmt.query_map([station_id, month_prefix], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
        })?;
        let mut map = HashMap::new();
        for row in rows {
            let (fecha, count) = row?;
            map.insert(fecha, count);
        }
        Ok(map)
    }

    fn get_daily_correction_counts(&self, station_id: &str, month_prefix: &str) -> Result<HashMap<String, i64>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let mut stmt = conn.prepare(
            "SELECT fecha, COUNT(*) FROM corrections WHERE station_id = ? AND fecha LIKE ? GROUP BY fecha"
        )?;
        let rows = stmt.query_map([station_id, month_prefix], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
        })?;
        let mut map = HashMap::new();
        for row in rows {
            let (fecha, count) = row?;
            map.insert(fecha, count);
        }
        Ok(map)
    }

    fn get_approved_corrections_for_date(&self, station_id: &str, fecha: &str) -> Result<Vec<(String, String, String)>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;
        let mut stmt = conn.prepare(
            "SELECT hora, campo, valor_corregido FROM corrections \
             WHERE station_id = ? AND fecha = ? AND estado = 'aprobado'"
        )?;
        let rows = stmt.query_map([station_id, fecha], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?))
        })?;
        let mut result = Vec::new();
        for row in rows {
            result.push(row?);
        }
        Ok(result)
    }

    fn get_person_summary(&self, station_id: Option<String>, year: Option<String>, month: Option<String>) -> Result<Vec<PersonSummaryRow>, AppError> {
        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;

        let mut map: HashMap<String, PersonSummaryRow> = HashMap::new();

        let mut err_query = "SELECT marcado_por, COUNT(*) FROM error_marks WHERE 1=1".to_string();
        let mut err_args: Vec<String> = Vec::new();

        if let Some(ref st) = station_id {
            if !st.is_empty() {
                err_query.push_str(" AND station_id = ?");
                err_args.push(st.clone());
            }
        }

        let y = year.as_deref().unwrap_or("");
        let m = month.as_deref().unwrap_or("");

        if !y.is_empty() && !m.is_empty() {
            err_query.push_str(" AND fecha LIKE ?");
            err_args.push(format!("{}-{}-%", y, m));
        } else if !y.is_empty() {
            err_query.push_str(" AND fecha LIKE ?");
            err_args.push(format!("{}-%", y));
        } else if !m.is_empty() {
            err_query.push_str(" AND fecha LIKE ?");
            err_args.push(format!("%-{}-%", m));
        }

        err_query.push_str(" GROUP BY marcado_por");

        let mut err_stmt = conn.prepare(&err_query)?;
        let err_rows = err_stmt.query_map(rusqlite::params_from_iter(err_args.iter()), |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?))
        })?;

        for r in err_rows {
            let (persona, count) = r?;
            map.insert(persona.clone(), PersonSummaryRow {
                persona,
                errores_marcados: count,
                correcciones_propuestas: 0,
                correcciones_aprobadas: 0,
            });
        }

        let mut corr_query = "SELECT corregido_por, COUNT(*), SUM(CASE WHEN estado = 'aprobado' THEN 1 ELSE 0 END) FROM corrections WHERE 1=1".to_string();
        let mut corr_args: Vec<String> = Vec::new();

        if let Some(ref st) = station_id {
            if !st.is_empty() {
                corr_query.push_str(" AND station_id = ?");
                corr_args.push(st.clone());
            }
        }

        let y = year.as_deref().unwrap_or("");
        let m = month.as_deref().unwrap_or("");

        if !y.is_empty() && !m.is_empty() {
            corr_query.push_str(" AND fecha LIKE ?");
            corr_args.push(format!("{}-{}-%", y, m));
        } else if !y.is_empty() {
            corr_query.push_str(" AND fecha LIKE ?");
            corr_args.push(format!("{}-%", y));
        } else if !m.is_empty() {
            corr_query.push_str(" AND fecha LIKE ?");
            corr_args.push(format!("%-{}-%", m));
        }

        corr_query.push_str(" GROUP BY corregido_por");

        let mut corr_stmt = conn.prepare(&corr_query)?;
        let corr_rows = corr_stmt.query_map(rusqlite::params_from_iter(corr_args.iter()), |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?, row.get::<_, i64>(2)?))
        })?;

        for r in corr_rows {
            let (persona, total, aprobadas) = r?;
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audit::{Correction, ErrorMark};
    use std::sync::atomic::{AtomicUsize, Ordering};

    static TEST_DB_COUNTER: AtomicUsize = AtomicUsize::new(0);

    fn setup_pool() -> Pool<SqliteConnectionManager> {
        let n = TEST_DB_COUNTER.fetch_add(1, Ordering::SeqCst);
        let mut path = std::env::temp_dir();
        path.push(format!("arca_audit_test_{}_{}.db", std::process::id(), n));
        let _ = std::fs::remove_file(&path);

        let manager = SqliteConnectionManager::file(&path);
        let pool = Pool::new(manager).unwrap();

        let conn = pool.get().unwrap();
        conn.execute_batch(
            r#"
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
            "#,
        )
        .unwrap();

        pool
    }

    fn insert_station(conn: &rusqlite::Connection, id: &str) {
        conn.execute(
            "INSERT INTO stations (id, name, provincia, latitud, longitud, elevacion, ch) VALUES (?, ?, ?, ?, ?, ?, ?)",
            params![id, "Test Station", "Test", 0.0, 0.0, 0.0, 0.0],
        )
        .unwrap();
    }

    #[test]
    fn test_new_creates_repository() {
        let pool = setup_pool();
        let repo = SqliteAuditRepository::new(pool);
        // Repository creation itself is the assertion; we only need it to compile and hold the pool.
        let _ = repo;
    }

    #[test]
    fn test_mark_error_inserts_error_mark() {
        let pool = setup_pool();
        let repo = SqliteAuditRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
            insert_station(&conn, "ST001");
        }

        let mark = ErrorMark {
            id: None,
            station_id: "ST001".to_string(),
            fecha: "2024-01-01".to_string(),
            hora: "12".to_string(),
            campo: "temperatura".to_string(),
            tipo_error: "fuera_rango".to_string(),
            nota: Some("nota".to_string()),
            marcado_por: "analista".to_string(),
            created_at: None,
        };

        let id = repo.mark_error(&mark).unwrap();
        assert!(id > 0);

        let marks = repo.get_error_marks("ST001", "2024-01-01").unwrap();
        assert_eq!(marks.len(), 1);
        assert_eq!(marks[0].campo, "temperatura");
    }

    #[test]
    fn test_unmark_error_removes_error_mark() {
        let pool = setup_pool();
        let repo = SqliteAuditRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
            insert_station(&conn, "ST002");
        }

        let mark = ErrorMark {
            id: None,
            station_id: "ST002".to_string(),
            fecha: "2024-02-01".to_string(),
            hora: "06".to_string(),
            campo: "humedad".to_string(),
            tipo_error: "inconsistencia".to_string(),
            nota: None,
            marcado_por: "analista".to_string(),
            created_at: None,
        };

        let id = repo.mark_error(&mark).unwrap();
        repo.unmark_error(id).unwrap();

        let marks = repo.get_error_marks("ST002", "2024-02-01").unwrap();
        assert!(marks.is_empty());
    }

    #[test]
    fn test_get_error_report_returns_correct_counts() {
        let pool = setup_pool();
        let repo = SqliteAuditRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
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
            justificacion: "correccion".to_string(),
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
        assert_eq!(report[0].valor_original.as_deref(), Some("1013"));
        assert_eq!(report[0].estado.as_deref(), Some("pendiente"));
    }

    #[test]
    fn test_get_daily_error_counts_returns_aggregated_data() {
        let pool = setup_pool();
        let repo = SqliteAuditRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
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

        let counts = repo.get_daily_error_counts("ST004", "2024-04-%").unwrap();
        assert_eq!(counts.get("2024-04-10"), Some(&3));
    }

    #[test]
    fn test_get_person_summary_returns_person_stats() {
        let pool = setup_pool();
        let repo = SqliteAuditRepository::new(pool);
        {
            let conn = repo.pool.get().unwrap();
            insert_station(&conn, "ST005");
        }

        let mark = ErrorMark {
            id: None,
            station_id: "ST005".to_string(),
            fecha: "2024-05-01".to_string(),
            hora: "00".to_string(),
            campo: "viento".to_string(),
            tipo_error: "tipo".to_string(),
            nota: None,
            marcado_por: "alice".to_string(),
            created_at: None,
        };
        repo.mark_error(&mark).unwrap();

        let correction = Correction {
            id: None,
            station_id: "ST005".to_string(),
            fecha: "2024-05-01".to_string(),
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
        repo.propose_correction(&correction).unwrap();

        let summary = repo
            .get_person_summary(Some("ST005".to_string()), Some("2024".to_string()), Some("05".to_string()))
            .unwrap();
        assert_eq!(summary.len(), 1);
        assert_eq!(summary[0].persona, "alice");
        assert_eq!(summary[0].errores_marcados, 1);
        assert_eq!(summary[0].correcciones_propuestas, 1);
        assert_eq!(summary[0].correcciones_aprobadas, 1);
    }
}
