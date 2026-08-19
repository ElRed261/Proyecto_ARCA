use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

/// Centralized ARCA path convention — single owner for all filesystem paths.
///
/// `modulo` is always `"synop"` for synoptic observations; the constant is exposed
/// via `SYNOP_MODULE` to avoid stringly-typed drift (`"synoptic"`, `"Resumen_Mensual_Synop"`).
pub const SYNOP_MODULE: &str = "synop";

/// Documents/ARCA/{modulo} with ARCA_BASE_DIR env override for integration tests.
pub fn arca_base_dir(app_handle: &AppHandle, modulo: &str) -> PathBuf {
    if let Ok(test_base) = std::env::var("ARCA_BASE_DIR") {
        return PathBuf::from(test_base).join(modulo);
    }
    let mut path = app_handle.path().document_dir().unwrap_or_else(|_| {
        let mut fallback = PathBuf::from(".");
        #[cfg(target_os = "windows")]
        {
            if let Ok(home) = std::env::var("USERPROFILE") {
                fallback = PathBuf::from(home);
            }
        }
        #[cfg(any(target_os = "macos", target_os = "linux"))]
        {
            if let Ok(home) = std::env::var("HOME") {
                fallback = PathBuf::from(home);
                fallback.push("Documents");
            }
        }
        fallback
    });
    path.push("ARCA");
    path.push(modulo);
    path
}

/// Backward-compat alias (Fase 1 call sites used `get_arca_base_dir`).
pub fn get_arca_base_dir(app_handle: &AppHandle, modulo: &str) -> PathBuf {
    arca_base_dir(app_handle, modulo)
}

/// Pure path join: base/{station}/{year}/{month} — no I/O.
pub fn station_dir(base: &Path, station: &str, year: &str, month: &str) -> PathBuf {
    base.join(station).join(year).join(month)
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
    let path = station_dir(base, station_code, year, month);
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

/// Create a timestamped backup and rotate to keep the 10 most recent.
pub fn create_backup(filepath: &Path, station_code: &str, app_handle: &AppHandle) -> Option<String> {
    if !filepath.exists() {
        return None;
    }
    let backup_dir = get_backups_dir(app_handle).join(station_code);
    if !backup_dir.exists() {
        let _ = fs::create_dir_all(&backup_dir);
    }
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();
    let filename = filepath.file_stem().and_then(|s| s.to_str()).unwrap_or("backup");
    let backup_name = format!("{}.{}.bak", filename, timestamp);
    let backup_path = backup_dir.join(&backup_name);
    if fs::copy(filepath, &backup_path).is_ok() {
        if let Ok(entries) = fs::read_dir(&backup_dir) {
            let mut backups = Vec::new();
            for entry in entries.flatten() {
                if let Ok(metadata) = entry.metadata() {
                    let name = entry.file_name().to_string_lossy().to_string();
                    if name.starts_with(filename) && name.ends_with(".bak") {
                        if let Ok(time) = metadata.modified() {
                            backups.push((time, entry.path()));
                        }
                    }
                }
            }
            backups.sort_by(|a, b| b.0.cmp(&a.0));
            for old in backups.iter().skip(10) {
                let _ = fs::remove_file(&old.1);
            }
        }
        return Some(backup_path.to_string_lossy().to_string());
    }
    None
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
