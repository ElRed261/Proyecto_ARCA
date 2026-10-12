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

/// P3.2 — resultado del emisión dual tras un save exitoso.
#[derive(Debug, Serialize)]
pub struct OnlineEmit {
    pub configured: bool,
    pub saved_online: bool,
    pub error: Option<String>,
}

/// Núcleo testeable: si `online_root` está configurado, copia el archivo
/// offline (que DEBE existir tras un save exitoso) a la raíz online. En
/// fallo encola en `conn`. Sin online_root configurado → no-op honesto.
#[allow(clippy::too_many_arguments)]
pub fn emit_after_save_core(
    conn: &Connection,
    offline_root: Option<&std::path::Path>,
    online_root: Option<&std::path::Path>,
    module: &str,
    station_code: &str,
    year: &str,
    month: &str,
    filename: &str,
) -> OnlineEmit {
    let Some(online) = online_root else {
        return OnlineEmit { configured: false, saved_online: false, error: None };
    };
    let offline_root = offline_root.unwrap_or_else(|| std::path::Path::new(""));
    let relative_path = format!("{}/{}/{}/{}/{}", module, station_code, year, month, filename);
    let source = offline_root.join(&relative_path);
    let target = online.join(&relative_path);

    match emit_copy(&source, &target) {
        Ok(_wrote) => {
            // éxito: cualquier fila pendiente de ESTE archivo queda sincronizada
            let now_ms = chrono::Utc::now().timestamp_millis();
            let _ = conn.execute(
                "UPDATE sync_pending SET synced_at=CURRENT_TIMESTAMP, attempts=0, last_error=NULL,
                 last_attempt_ms=? WHERE module=? AND station_code=? AND relative_path=? AND synced_at IS NULL",
                params![now_ms, module, station_code, relative_path],
            );
            OnlineEmit { configured: true, saved_online: true, error: None }
        }
        Err(e) => {
            let enqueued = enqueue_pending(
                conn,
                &SyncRow {
                    module: module.to_string(),
                    station_code: station_code.to_string(),
                    relative_path: relative_path.clone(),
                    source_path: source.to_string_lossy().to_string(),
                },
            );
            OnlineEmit {
                configured: true,
                saved_online: false,
                error: Some(match enqueued {
                    Ok(()) => e,
                    Err(qe) => format!("{} (además falló el enqueue: {})", e, qe),
                }),
            }
        }
    }
}

/// P3.2 — pegamento Tauri: resuelve roots (env > PathProfile > default con la
/// MISMA cadena de P1.2, sin la capa {modulo}, que viaja en relative_path),
/// y emite dual tras un save offline exitoso. Jamás bloquea el save.
pub fn emit_dual_after_save(
    app_handle: &tauri::AppHandle,
    module: &str,
    station_code: &str,
    fecha: &str,
) -> OnlineEmit {
    use crate::db::get_db_path;

    let db_path = get_db_path(app_handle);
    let conn = match Connection::open(&db_path) {
        Ok(c) => c,
        Err(e) => {
            return OnlineEmit {
                configured: false,
                saved_online: false,
                error: Some(format!("sin acceso a la DB de sync: {}", e)),
            };
        }
    };

    // modo test / override env: sin dual (aislamiento de tests)
    if std::env::var("ARCA_BASE_DIR").is_ok() {
        return OnlineEmit { configured: false, saved_online: false, error: None };
    }

    let profile = crate::infrastructure::storage::paths_config::get_path_config_db(&conn)
        .unwrap_or_default();

    let default_base =
        crate::infrastructure::storage::paths_config::default_documents_root_public(app_handle);
    let offline_root = match &profile {
        Some(p) if !p.offline_root.is_empty() => std::path::PathBuf::from(&p.offline_root),
        _ => default_base,
    };
    let online_root: Option<std::path::PathBuf> = profile
        .as_ref()
        .and_then(|p| p.online_root.as_ref())
        .filter(|s| !s.is_empty())
        .map(std::path::PathBuf::from);

    let station_norm = crate::infrastructure::storage::normalize_station_code(station_code);
    let year_month = crate::json_handler::utils::parse_date_parts(fecha)
        .map_err(|e| format!("fecha inválida para sync dual: {}", e));
    let (year, month) = match year_month {
        Ok(v) => v,
        Err(e) => {
            return OnlineEmit {
                configured: online_root.is_some(),
                saved_online: false,
                error: Some(e),
            };
        }
    };
    let filename = format!(
        "{}{}.json",
        station_norm,
        crate::json_handler::utils::format_date_for_filename(fecha)
    );

    emit_after_save_core(
        &conn,
        Some(offline_root.as_path()),
        online_root.as_deref(),
        module,
        &station_norm,
        &year,
        &month,
        &filename,
    )
}

/// Comando: reintentar pendientes. admin/encargado. force=true = botón manual.
#[tauri::command]
pub fn retry_pending_sync(
    app_handle: tauri::AppHandle,
    store: tauri::State<'_, crate::modules::auth::SessionStore>,
    token: String,
    force: bool,
) -> Result<SyncOutcome, String> {
    crate::modules::auth::require_role(&store, &token, &["admin", "encargado"])
        .map_err(|e| e.to_string())?;

    let profile = paths_config_lookup(&app_handle)?;
    let (offline_root, online_root) = match profile {
        (Some(p), _) if !p.offline_root.is_empty() => (
            Some(crate::infrastructure::storage::paths_config::offline_base_dir(
                &app_handle,
                "",
            )?),
            p.online_root
                .as_ref()
                .filter(|s| !s.is_empty())
                .map(std::path::PathBuf::from),
        ),
        (None, docs) => (docs.map(base_of), None),
        _ => (None, None),
    };
    let offline_root = offline_root.unwrap_or_else(|| std::path::PathBuf::from(""));

    let conn = Connection::open(crate::db::get_db_path(&app_handle)).map_err(|e| e.to_string())?;
    let Some(online) = online_root else {
        return Ok(SyncOutcome { attempted: 0, uploaded: 0, marked_synced: 0, last_error: None });
    };
    retry_pending_sync_core(
        &conn,
        offline_root.to_string_lossy().as_ref(),
        online.to_string_lossy().as_ref(),
        force,
    )
}

type ProfileDoc = (Option<crate::infrastructure::storage::paths_config::PathProfile>,
                  Option<std::path::PathBuf>);

fn paths_config_lookup(
    app_handle: &tauri::AppHandle,
) -> Result<ProfileDoc, String> {
    let conn = Connection::open(crate::db::get_db_path(app_handle)).map_err(|e| e.to_string())?;
    let profile = crate::infrastructure::storage::paths_config::get_path_config_db(&conn)
        .unwrap_or_default();
    let docs = if let Ok(env_base) = std::env::var("ARCA_BASE_DIR") {
        Some(std::path::PathBuf::from(env_base))
    } else {
        Some(crate::infrastructure::storage::paths_config::default_documents_root_public(app_handle))
    };
    Ok((profile, docs))
}

fn base_of(p: std::path::PathBuf) -> std::path::PathBuf {
    p
}

/// Comando: status del panel de sincronización. Cualquier usuario autenticado.
#[tauri::command]
pub fn get_sync_status(
    app_handle: tauri::AppHandle,
    store: tauri::State<'_, crate::modules::auth::SessionStore>,
    token: String,
) -> Result<SyncStatus, String> {
    store.validate_session(&token).map_err(|e| e.to_string())?;
    let conn = Connection::open(crate::db::get_db_path(&app_handle)).map_err(|e| e.to_string())?;
    get_sync_status_core(&conn)
}
