//! paths_config — configuración central de rutas de guardado (P1.1).
//!
//! Un solo dueño del perfil de rutas: raíz offline, raíz online (carpeta
//! sincronizada por Drive Desktop), edad máxima de backups y carpeta de resúmenes.
//! Persistido en la tabla `app_config` bajo la clave `path_config` como JSON.
//!
//! Contratos:
//! - Solo admin puede SETEAR; cualquier usuario autenticado puede LEER.
//! - `validate_profile` valida rutas reales de forma pura (testeable sin Tauri).
//! - La resolución efectiva (env override > config > default) vive en P1.2.

use crate::db::get_db_path;
use crate::modules::auth::{require_role, SessionStore};
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use tauri::{command, AppHandle};

/// Clave KV donde vive el PathProfile serializado.
const KEY: &str = "path_config";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PathProfile {
    /// Raíz offline ("" = sin configurar → default Documents/ARCA).
    #[serde(default)]
    pub offline_root: String,
    /// Raíz online opcional: carpeta local sincronizada por Google Drive Desktop.
    /// None = guardado dual-destination desactivado.
    #[serde(default)]
    pub online_root: Option<String>,
    /// Edad máxima de backups en días (None = política default del writer).
    #[serde(default)]
    pub backups_max_age_days: Option<u32>,
    /// Carpeta de resúmenes mensuales (None = derivar de offline_root).
    #[serde(default)]
    pub summaries_dir: Option<String>,
}

impl PathProfile {
    /// Perfil solo-offline con la raíz dada (útil en tests y primer arranque).
    pub fn default_offline_only(offline_root: &str) -> Self {
        Self {
            offline_root: offline_root.to_string(),
            online_root: None,
            backups_max_age_days: None,
            summaries_dir: None,
        }
    }
}

/// Valida el perfil con reglas reales (pura — testeable sin Tauri).
pub fn validate_profile(profile: &PathProfile) -> Result<(), String> {
    if !profile.offline_root.is_empty() && !es_ruta_absoluta(&profile.offline_root) {
        return Err(format!(
            "offline_root debe ser una ruta absoluta (se recibió '{}')",
            profile.offline_root
        ));
    }

    if let Some(online) = &profile.online_root {
        if online.is_empty() {
            return Err("online_root, si se define, no puede ser vacío".to_string());
        }
        if !es_ruta_absoluta(online) {
            return Err(format!(
                "online_root debe ser una ruta absoluta (se recibió '{}')",
                online
            ));
        }
        if !profile.offline_root.is_empty()
            && normalizar(online) == normalizar(&profile.offline_root)
        {
            return Err(
                "online_root y offline_root no pueden apuntar a la misma carpeta: \
                 se perdería la separación local/online y el conflicto por Drive sync"
                    .to_string(),
            );
        }
    }

    if let Some(summaries) = &profile.summaries_dir {
        if !summaries.is_empty() && !es_ruta_absoluta(summaries) {
            return Err(format!(
                "summaries_dir debe ser una ruta absoluta (se recibió '{}')",
                summaries
            ));
        }
        if !summaries.is_empty()
            && !profile.offline_root.is_empty()
            && normalizar(summaries) == normalizar(&profile.offline_root)
        {
            return Err(
                "summaries_dir no puede coincidir con offline_root: los resúmenes son \
                 documentos de distinto ciclo de vida que las observaciones crudas"
                    .to_string(),
            );
        }
    }

    Ok(())
}

/// Windows: `C:\...` / `D:/...` cuenta como absoluta; Unix: leading `/`.
fn es_ruta_absoluta(p: &str) -> bool {
    if p.starts_with('/') {
        return true;
    }
    let b = p.as_bytes();
    b.len() >= 3
        && b[0].is_ascii_alphabetic()
        && b[1] == b':'
        && (b[2] == b'\\' || b[2] == b'/')
}

/// Normalización comparable: sin trailing slashes, case-insensitive.
/// (Los FS de Windows/macOS son case-insensitive; unificar evita falsos positivos).
fn normalizar(p: &str) -> String {
    let trimmed = p.trim_end_matches(['/', '\\']);
    if trimmed.len() >= 2 {
        let b = trimmed.as_bytes();
        return format!("{}{}", b[0].to_ascii_lowercase(), &trimmed[1..]);
    }
    trimmed.to_string()
}

/// Lee el perfil de rutas desde la conexión dada (None si nunca se configuró).
pub fn get_path_config_db(conn: &Connection) -> Result<Option<PathProfile>, String> {
    let value: Option<String> = conn
        .query_row(
            "SELECT value FROM app_config WHERE key = ?",
            params![KEY],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| format!("Error leyendo path_config: {}", e))?;

    match value {
        Some(json) => serde_json::from_str(&json)
            .map(Some)
            .map_err(|e| format!("path_config corrupto: {}", e)),
        None => Ok(None),
    }
}

/// Escribe el perfil SIN control de rol (uso interno; el rol se controla aparte).
pub fn set_path_config_db(conn: &Connection, profile: &PathProfile) -> Result<(), String> {
    validate_profile(profile)?;
    let json = serde_json::to_string(profile).map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT OR REPLACE INTO app_config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        params![KEY, json],
    )
    .map_err(|e| format!("Error guardando path_config: {}", e))?;
    Ok(())
}

/// Guarda con control de rol: requiere sesión de admin.
/// Función usada por el comando Tauri y por los tests de autorización.
pub fn set_path_config_checked(
    store: &SessionStore,
    token: &str,
    conn: &Connection,
    profile: &PathProfile,
) -> Result<(), String> {
    require_role(store, token, &["admin"]).map_err(|e| e.to_string())?;
    set_path_config_db(conn, profile)
}

/// Comando: cualquier usuario autenticado puede leer el perfil.
#[command]
pub fn get_path_config(
    app_handle: AppHandle,
    store: tauri::State<'_, SessionStore>,
    token: String,
) -> Result<Option<PathProfile>, String> {
    store.validate_session(&token).map_err(|e| e.to_string())?;
    let conn = Connection::open(get_db_path(&app_handle)).map_err(|e| e.to_string())?;
    get_path_config_db(&conn)
}

/// Comando: solo admin puede guardar el perfil.
#[command]
pub fn set_path_config(
    app_handle: AppHandle,
    store: tauri::State<'_, SessionStore>,
    token: String,
    profile: PathProfile,
) -> Result<(), String> {
    let conn = Connection::open(get_db_path(&app_handle)).map_err(|e| e.to_string())?;
    set_path_config_checked(&store, &token, &conn, &profile)
}
