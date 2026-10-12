//! sync_queue — P3: cola offline-first para el guardado dual-destination.
//!
//! El save offline SIEMPRE escribe primero. Si la raíz online (Drive Desktop)
//! está disponible, el archivo se emite también allí; si no, la fila queda
//! pendiente en SQLite y un retry la sube cuando vuelve. Contenido idéntico
//! no se re-submite (sha256). Nunca se pierde una observación por falta de red.

use rusqlite::{params, Connection};
use serde::Serialize;

/// P3.1 — migración de la tabla. La lista vive en db.rs: registrar aquí la
/// sentencia también llamado desde db::get_migrations para no duplicar.
pub const MIGATION_SQL: &str =
    "CREATE TABLE IF NOT EXISTS sync_pending (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module TEXT NOT NULL,
        station_code TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        source_path TEXT NOT NULL,
        sha256 TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        last_attempt_at DATETIME,
        last_attempt_ms INTEGER,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        synced_at DATETIME,
        UNIQUE(module, station_code, relative_path)
    );
    CREATE INDEX IF NOT EXISTS idx_sync_pending_unsent ON sync_pending(synced_at, created_at);";

/// Fila a encolar (sin metadatos: los completa el core).
#[derive(Debug, Clone)]
pub struct SyncRow {
    pub module: String,
    pub station_code: String,
    pub relative_path: String,
    pub source_path: String,
}

/// Resultado de una pasada de retry.
#[derive(Debug, Serialize)]
pub struct SyncOutcome {
    pub attempted: u32,
    pub uploaded: u32,
    pub marked_synced: u32,
    pub last_error: Option<String>,
}

/// Filas de error exponibles en el status (últimas rear).
#[derive(Debug, Serialize)]
pub struct SyncErrorRow {
    pub station_code: String,
    pub relative_path: String,
    pub detail: String,
}

/// Estado consultable del panel de sincronización (P3.4).
#[derive(Debug, Serialize)]
pub struct SyncStatus {
    pub pending: u64,
    pub synced: u64,
    pub last_attempt: Option<String>,
    pub last_errors: Vec<SyncErrorRow>,
}

fn sha256_hex_file(path: &std::path::Path) -> Option<String> {
    use sha2::{Digest, Sha256};
    std::fs::read(path)
        .ok()
        .map(|bytes| {
            let mut hasher = Sha256::new();
            hasher.update(&bytes);
            format!("{:x}", hasher.finalize())
        })
}

/// Encola (INSERT OR IGNORE: la fila única por (module, station, path) evita
/// duplicados entre saves consecutivos) con el sha256 del archivo fuente.
pub fn enqueue_pending(conn: &Connection, row: &SyncRow) -> Result<(), String> {
    let sha = sha256_hex_file(std::path::Path::new(&row.source_path));
    conn.execute(
        "INSERT OR IGNORE INTO sync_pending
            (module, station_code, relative_path, source_path, sha256)
         VALUES (?, ?, ?, ?, ?)",
        params![row.module, row.station_code, row.relative_path, row.source_path, sha],
    )
    .map_err(|e| format!("error encolando sync_pending: {}", e))?;
    Ok(())
}

/// P3.4 — status agregado para la UI.
pub fn get_sync_status_core(conn: &Connection) -> Result<SyncStatus, String> {
    let pending: u64 = conn
        .query_row("SELECT COUNT(*) FROM sync_pending WHERE synced_at IS NULL", [], |r| r.get(0))
        .map_err(|e| e.to_string())?;
    let synced: u64 = conn
        .query_row("SELECT COUNT(*) FROM sync_pending WHERE synced_at IS NOT NULL", [], |r| r.get(0))
        .map_err(|e| e.to_string())?;
    let last_attempt: Option<String> = conn
        .query_row(
            "SELECT MAX(last_attempt_at) FROM sync_pending WHERE last_attempt_at IS NOT NULL",
            [],
            |r| r.get(0),
        )
        .map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare(
            "SELECT station_code, relative_path, IFNULL(last_error,'') FROM sync_pending
             WHERE synced_at IS NULL AND last_error IS NOT NULL
             ORDER BY last_attempt_at DESC LIMIT 5",
        )
        .map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |r| {
            Ok(SyncErrorRow {
                station_code: r.get(0)?,
                relative_path: r.get(1)?,
                detail: r.get(2)?,
            })
        })
        .map_err(|e| e.to_string())?;
    let last_errors: Vec<SyncErrorRow> = rows
        .filter_map(|r| r.ok())
        .collect();
    Ok(SyncStatus { pending, synced, last_attempt, last_errors })
}

/// P3.3 — una pasada de retry sobre las filas pendientes.
///
/// - `force=false` respeta backoff: skip si last_attempt es más reciente
///   que min(2^attempts, 60) minutos.
/// - `force=true` (botón manual) procesa todo lo pendiente ahora.
/// - Contenido idéntico online (sha igual) marca synced SIN rescribir.
pub fn retry_pending_sync_core(
    conn: &Connection,
    offline_root: &str,
    online_root: &str,
    force: bool,
) -> Result<SyncOutcome, String> {
    let mut stmt = conn
        .prepare(
            "SELECT module, station_code, relative_path, source_path, IFNULL(sha256,''), attempts
             FROM sync_pending WHERE synced_at IS NULL ORDER BY created_at",
        )
        .map_err(|e| e.to_string())?;
    let rows = stmt
        .query_map([], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, String>(3)?,
                r.get::<_, String>(4)?,
                r.get::<_, i64>(5)?,
            ))
        })
        .map_err(|e| e.to_string())?;
    let all: Vec<_> = rows.filter_map(|r| r.ok()).collect();

    let mut outcome = SyncOutcome { attempted: 0, uploaded: 0, marked_synced: 0, last_error: None };
    let now_ms = chrono::Utc::now().timestamp_millis();

    for (module, station_code, relative_path, _source_path, _stored_sha, attempts) in all {
        // backoff: la ventana crece con los intentos (2^attempts MINUTOS,
        // tope 60 min). Sin backoff la cola martillaría la raíz caída.
        if !force && attempts > 0 {
            let window_secs: i64 = (1i64 << attempts.clamp(0, 59)).saturating_mul(60).min(60 * 60);
            let en_ventana: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM sync_pending
                     WHERE module=? AND station_code=? AND relative_path=?
                       AND (last_attempt_ms IS NOT NULL AND ? - last_attempt_ms < ?)",
                    params![module, station_code, relative_path, now_ms, window_secs * 1000],
                    |r| r.get(0),
                )
                .unwrap_or(0);
            if en_ventana > 0 {
                continue; // aún dentro de la ventana de backoff: no martillear
            }
        }

        let source = std::path::Path::new(offline_root).join(&relative_path);
        let target = std::path::Path::new(online_root).join(&relative_path);
        outcome.attempted += 1;

        let res = emit_copy(&source, &target);
        match res {
            Ok(wrote) => {
                if wrote {
                    outcome.uploaded += 1;
                }
                conn.execute(
                    "UPDATE sync_pending SET synced_at=CURRENT_TIMESTAMP, attempts=0,
                     last_error=NULL, last_attempt_ms=? WHERE module=? AND station_code=? AND relative_path=?",
                    params![now_ms, module, station_code, relative_path],
                )
                .map_err(|e| e.to_string())?;
                outcome.marked_synced += 1;
            }
            Err(e) => {
                let new_attempts = attempts + 1;
                conn.execute(
                    "UPDATE sync_pending SET attempts=?, last_error=?, last_attempt_ms=?,
                     last_attempt_at=CURRENT_TIMESTAMP
                     WHERE module=? AND station_code=? AND relative_path=?",
                    params![new_attempts, e, now_ms, module, station_code, relative_path],
                )
                .map_err(|err| err.to_string())?;
                outcome.last_error = Some(e);
            }
        }
    }
    Ok(outcome)
}

/// Copia el archivo fuente al destino online (atómicamente).
/// Ok(true) = escribió; Ok(false) = el destino ya tiene el contenido exacto.
fn emit_copy(source: &std::path::Path, target: &std::path::Path) -> Result<bool, String> {
    use sha2::Digest;
    use std::fs;
    if !source.exists() {
        return Err(format!("source desapareció: {:?}", source));
    }
    let contenido = fs::read(source).map_err(|e| format!("error leyendo {:?}: {}", source, e))?;

    // mismo sha en destino → nada que hacer (ya sincronizado)
    if let Ok(dest_bytes) = fs::read(target) {
        let mut h1 = sha2::Sha256::new();
        h1.update(&contenido);
        let mut h2 = sha2::Sha256::new();
        h2.update(&dest_bytes);
        if format!("{:x}", h1.finalize()) == format!("{:x}", h2.finalize()) {
            return Ok(false);
        }
    }

    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|e| {
            format!("error creando dirs online {:?}: {}", parent, e)
        })?;
    }
    super::write_guard::atomic_write_sync(
        target,
        &String::from_utf8_lossy(&contenido),
    )
    .map_err(|e| format!("error escribiendo {:?}: {}", target, e))?;
    Ok(true)
}
