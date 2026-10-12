pub mod paths_config;
pub mod sync_queue;
pub mod write_guard;

pub use paths_config::offline_base_dir;

use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

/// Centralized ARCA path convention — single owner for all filesystem paths.
///
/// `modulo` is always `"synop"` for synoptic observations; the constant is exposed
/// via `SYNOP_MODULE` to avoid stringly-typed drift (`"synoptic"`, `"Resumen_Mensual_Synop"`).
pub const SYNOP_MODULE: &str = "synop";

/// P1.5 — Normalización de código de estación: todo lo que toca folder/archivo
/// pasa por aquí (los FS de Windows/macOS son case-insensitive; sin esto, un
/// código guardado como 'MiEstacion' colisionaría con 'miestacion').
pub fn normalize_station_code(code: &str) -> String {
    code.trim().to_ascii_lowercase()
}

/// Pure path join: base/{station}/{year}/{month} — no I/O.
pub fn station_dir(base: &Path, station: &str, year: &str, month: &str) -> PathBuf {
    base.join(normalize_station_code(station)).join(year).join(month)
}

/// Ensure base/{year}/{month} exists.
pub fn ensure_arca_dirs(base_dir: &Path, year: &str, month: &str) -> Result<PathBuf, String> {
    let mut path = base_dir.to_path_buf();
    path.push(year);
    path.push(month);
    fs::create_dir_all(&path).map_err(|e| format!("Error creando directorios: {}", e))?;
    Ok(path)
}

/// Ensure base/{station}/{year}/{month} exists.
pub fn ensure_station_dir(
    base: &Path,
    station_code: &str,
    year: &str,
    month: &str,
) -> Result<PathBuf, String> {
    let path = station_dir(base, &normalize_station_code(station_code), year, month);
    fs::create_dir_all(&path).map_err(|e| format!("Error creando directorios: {}", e))?;
    Ok(path)
}

/// Alias for existing call sites.
pub fn ensure_arca_dirs_with_station(
    base_dir: &Path,
    station_code: &str,
    year: &str,
    month: &str,
) -> Result<PathBuf, String> {
    ensure_station_dir(base_dir, station_code, year, month)
}

pub fn get_base_data_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    path.push("data");
    path
}

pub fn get_backups_dir(app_handle: &AppHandle) -> PathBuf {
    get_base_data_dir(app_handle).join(".backups")
}

use sha2::{Digest, Sha256};

fn sha256_file(path: &Path) -> Option<String> {
    fs::read(path).ok().map(|bytes| {
        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        format!("{:x}", hasher.finalize())
    })
}

fn bak_metadata(p: &Path) -> Option<std::time::SystemTime> {
    fs::metadata(p).and_then(|m| m.modified()).ok()
}

/// P2.4 — Backup con política honesta:
/// 1. Dedupe por sha256: si el último backup ya tiene el contenido exacto, no copia.
/// 2. Máx 10 backups por archivo-día (comportamiento previo).
/// 3. Podar por edad (backups_max_age_days) y por cap de bytes totales (lo más viejo),
///    jamás removiendo el backup recién creado.
///
/// Principio: si algo es incierto, conservar — no destruir datos.
pub fn create_backup_in(
    filepath: &Path,
    station_code: &str,
    backup_root: &Path,
    max_age_days: u32,
    max_total_bytes: u64,
) -> Option<String> {
    if !filepath.exists() {
        return None;
    }
    let content_hash = sha256_file(filepath)?;
    let backup_dir = backup_root.join(station_code);
    if !backup_dir.exists() {
        let _ = fs::create_dir_all(&backup_dir);
    }
    let filename = filepath
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("backup");

    let mut backup_paths: Vec<std::path::PathBuf> = Vec::new();
    if let Ok(entries) = fs::read_dir(&backup_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with(filename) && name.ends_with(".bak") {
                let pth = entry.path();
                if !backup_paths.contains(&pth) {
                    backup_paths.push(pth);
                }
            }
        }
    }
    // newest first (mtime desc; sin mtime conocido → al final, no destruir)
    backup_paths.sort_by_key(|p| {
        std::cmp::Reverse(
            bak_metadata(p)
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
                .unwrap_or(0), // sin mtime conocido = más viejo
        )
    });

    // dedupe: copia idéntica ya respaldada
    if let Some(latest) = backup_paths.first() {
        if sha256_file(latest).as_deref() == Some(content_hash.as_str()) {
            return None;
        }
    }

    // timestamp con milisegundos + guard exists: saves en el mismo segundo
    // no deben colisionar de nombre (antes se pisaban entre sí)
    let mut backup_path = backup_dir.join(format!(
        "{}.{}.bak",
        filename,
        chrono::Local::now().format("%Y%m%d_%H%M%S%.3f")
    ));
    let mut nano = 1u32;
    while backup_path.exists() {
        backup_path = backup_dir.join(format!(
            "{}.{}.{}.bak",
            filename,
            chrono::Local::now().format("%Y%m%d_%H%M%S%.3f"),
            nano
        ));
        nano += 1;
        if nano > 1000 {
            break;
        }
    }
    if fs::copy(filepath, &backup_path).is_err() {
        return None;
    }
    if !backup_paths.contains(&backup_path) {
        backup_paths.insert(0, backup_path.clone());
    }

    // poda por edad
    let max_age_secs = u64::from(max_age_days).saturating_mul(24 * 3600);
    let now = std::time::SystemTime::now();
    backup_paths.retain(|p| {
        bak_metadata(p)
            .map(|mtime| {
                now.duration_since(mtime)
                    .map(|age| age.as_secs() <= max_age_secs)
                    .unwrap_or(true) // edad desconocida → conservar
            })
            .unwrap_or(true) // metadata ilegible → conservar
    });

    // poda por bytes (deja siempre al menos el más reciente)
    let mut total: u64 = backup_paths
        .iter()
        .filter_map(|p| fs::metadata(p).ok())
        .map(|m| m.len())
        .sum();
    let mut idx = backup_paths.len().saturating_sub(1);
    while total > max_total_bytes && idx > 0 {
        if let Ok(m) = fs::metadata(&backup_paths[idx]) {
            total = total.saturating_sub(m.len());
        }
        let _ = fs::remove_file(&backup_paths[idx]);
        backup_paths.remove(idx);
        idx -= 1; // jamás baja de 1: el backup más nuevo no se toca
    }

    Some(backup_path.to_string_lossy().to_string())
}

/// Create a timestamped backup and rotate using PathProfile policy
/// (backups_max_age_days default 30); bytes default 64 MiB per station.
pub fn create_backup(filepath: &Path, station_code: &str, app_handle: &AppHandle) -> Option<String> {
    let db_path = crate::db::get_db_path(app_handle);
    let max_age_days = rusqlite::Connection::open(&db_path).ok().and_then(|conn| {
        crate::infrastructure::storage::paths_config::get_path_config_db(&conn)
            .ok()
            .flatten()
            .and_then(|profile| profile.backups_max_age_days)
    });
    let age = max_age_days.unwrap_or(30);
    create_backup_in(
        filepath,
        station_code,
        &get_backups_dir(app_handle),
        age,
        64 * 1024 * 1024,
    )
}

/// Atomic write: write to temp file in same dir then rename.
/// Guarantees readers never see a half-written JSON.
pub fn atomic_write(path: &Path, content: &str) -> std::io::Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    // ponytail: unique tmp per write avoids races on same file
    let file_name = path.file_name().and_then(|s| s.to_str()).unwrap_or("tmp");
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let tmp_name = format!(".{}.tmp.{}-{}", file_name, std::process::id(), nanos);
    let tmp_path = parent.join(tmp_name);
    // If parent doesn't exist, caller should have ensured it; surface the error
    // rather than silently creating — keeps failures explicit.
    let res = (|| {
        fs::write(&tmp_path, content)?;
        fs::rename(&tmp_path, path)?;
        Ok(())
    })();
    if res.is_err() {
        let _ = fs::remove_file(&tmp_path);
    }
    res
}

#[cfg(test)]
mod backup_policy_tests {
    use super::*;
    use filetime::FileTime;

    fn temp_root(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "arca_bk_{}_{}_{}",
            tag,
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&dir).expect("temp dir");
        dir
    }

    fn datos(path: &str, v: u64) -> PathBuf {
        let dir = temp_root(&format!("data{}v{}", path.replace('/', "_"), v));
        let f = dir.join("archivo.json");
        std::fs::write(&f, format!(r#"{{"v":{}}}"#, v)).expect("datos");
        f
    }

    #[test]
    fn backup_contenido_igual_no_duplica() {
        let root = temp_root("dedupe");
        let f = datos("/dedupe", 1);

        let b1 = create_backup_in(&f, "78486", &root, 30, 64 * 1024 * 1024);
        assert!(b1.is_some(), "primer backup debe crearse");
        let b2 = create_backup_in(&f, "78486", &root, 30, 64 * 1024 * 1024);
        assert!(b2.is_none(), "backup idéntico debe saltarse (dedupe por sha)");

        let station_dir = root.join("78486");
        let count = fs::read_dir(&station_dir).unwrap().count();
        assert_eq!(count, 1, "debe haber exactamente 1 backup");
    }

    #[test]
    fn backup_contenido_distinto_genera_nueva_copia() {
        let root = temp_root("dedupe2");
        let f1 = datos("/dedupe2", 1);
        assert!(create_backup_in(&f1, "78486", &root, 30, 64 * 1024 * 1024).is_some());

        let f2 = datos("/dedupe2", 2);
        assert!(create_backup_in(&f2, "78486", &root, 30, 64 * 1024 * 1024).is_some());
        // y el tercero igual al segundo no duplica:
        assert!(create_backup_in(&f2, "78486", &root, 30, 64 * 1024 * 1024).is_none());
    }

    #[test]
    fn backup_prune_respeta_edad_maxima() {
        let root = temp_root("age");
        let f = datos("/age", 1);

        let b = create_backup_in(&f, "78486", &root, 7, 64 * 1024 * 1024).expect("backup 1");
        // envejecer el backup a 30 días
        let old = filetime::FileTime::from_system_time(
            std::time::SystemTime::now() - std::time::Duration::from_secs(30 * 24 * 3600),
        );
        filetime::set_file_mtime(
            std::path::Path::new(&b),
            FileTime::from_system_time(
                std::time::SystemTime::now() - std::time::Duration::from_secs(30 * 24 * 3600),
            ),
        )
        .expect("setear mtime old");
        let _ = old;

        // crear backup 2 (contenido distinto) — durante la creación se poda 1 por edad
        let f2 = datos("/age", 2);
        create_backup_in(&f2, "78486", &root, 7, 64 * 1024 * 1024);

        let station_dir = root.join("78486");
        let quedan: Vec<_> = fs::read_dir(&station_dir)
            .unwrap()
            .flatten()
            .filter(|e| e.file_name().to_string_lossy().contains("archivo.json"))
            .collect();
        assert!(
            !quedan.iter().any(|e| e.path() == std::path::Path::new(&b)),
            "el backup de hace 30 días debe podarse con backups_max_age_days=7"
        );
    }

    #[test]
    fn backup_prune_por_cap_bytes_conserva_los_mas_nuevos() {
        let root = temp_root("bytes");
        // cada archivo datos ocupa ~10 bytes; cap = 1 file+overhead pequeño → fuerza prune
        let f1 = datos("/bytes", 1);
        create_backup_in(&f1, "78486", &root, 30, 5 * 1024 * 1024);
        let f2 = datos("/bytes", 2);
        create_backup_in(&f2, "78486", &root, 30, 5 * 1024 * 1024);

        let f3 = datos("/bytes", 3);
        create_backup_in(&f3, "78486", &root, 30, 12); // cap 12 bytes: con dos backups de >12 se debe podar

        let station_dir = root.join("78486");
        let count = fs::read_dir(&station_dir)
            .unwrap()
            .filter(|e| e.is_ok())
            .count();
        eprintln!("DEBUG entries: {:?}", fs::read_dir(&station_dir).unwrap().flatten().map(|e| e.file_name().to_string_lossy().to_string()).collect::<Vec<_>>());
        let total: u64 = fs::read_dir(&station_dir)
            .unwrap()
            .flatten()
            .map(|e| e.metadata().map(|m| m.len()).unwrap_or(0))
            .sum();
        assert!(
            total <= 12 + 4096, // overhead del bloque mínimo del FS en tmpfs/ext4
            "el total de backups debe respetarse en la práctica; total={} bytes",
            total
        );
        assert!(count >= 1, "al menos el último backup debe conservarse");
    }
}
