use crate::domain::models::{Correction, ErrorMark, ErrorReportRow, PersonSummaryRow};
use crate::infrastructure::error::AppError;
use crate::ports::AuditRepository;
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

        // La barrera real contra duplicados es el índice UNIQUE uq_error_marks_slot
        // (db.rs); aquí solo traducimos el conflicto a error de validación.
        // ponytail: ON CONFLICT reemplaza al COUNT previo que tenía carrera TOCTOU.
        let inserted = conn.execute(
            "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, nota, marcado_por) \
             VALUES (?, ?, ?, ?, ?, ?, ?) \
             ON CONFLICT(station_id, fecha, hora, campo) DO NOTHING",
            params![mark.station_id, mark.fecha, mark.hora, mark.campo, mark.tipo_error, mark.nota, mark.marcado_por],
        )?;

        if inserted == 0 {
            return Err(AppError::Validation("Este campo ya está marcado como error".to_string()));
        }

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

    fn get_person_summary(&self, station_id: Option<String>, year: Option<String>, month: Option<String>) -> Result<Vec<PersonSummaryRow>, AppError> {        let conn = self.pool.get().map_err(|e| AppError::Internal(e.to_string()))?;

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
    use crate::db::get_migrations;

    // ponytail: max_size(1) obligatorio — cada conexión de un pool :memory:
    // es una BD distinta; con una sola conexión todos comparten la misma.
    fn test_repo() -> SqliteAuditRepository {
        let manager = SqliteConnectionManager::memory();
        let pool = Pool::builder().max_size(1).build(manager).unwrap();
        let mut conn = pool.get().unwrap();
        get_migrations().to_latest(&mut conn).unwrap();
        SqliteAuditRepository::new(pool)
    }

    fn mark(hora: &str) -> ErrorMark {
        ErrorMark {
            id: None,
            station_id: "78451".into(),
            fecha: "2024-03-15".into(),
            hora: hora.into(),
            campo: "t_max".into(),
            tipo_error: "lectura".into(),
            nota: None,
            marcado_por: "tester".into(),
            created_at: None,
        }
    }

    #[test]
    fn duplicate_mark_is_rejected_by_unique_barrier() {
        let repo = test_repo();
        let first = repo.mark_error(&mark("08")).unwrap();
        assert!(first > 0);

        let dup = repo.mark_error(&mark("08"));
        assert!(
            matches!(dup, Err(AppError::Validation(ref msg)) if msg.contains("ya está marcado")),
            "expected validation error, got {dup:?}"
        );

        // distinta hora sí inserta
        assert!(repo.mark_error(&mark("09")).is_ok());
    }
}

