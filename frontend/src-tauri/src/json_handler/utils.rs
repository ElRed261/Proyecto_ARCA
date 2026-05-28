use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

/// Obtiene el directorio base de Documents/ARCA/{modulo}/
/// Funciona en Windows, macOS y Linux
pub fn get_arca_base_dir(app_handle: &AppHandle, modulo: &str) -> PathBuf {
    let mut path = app_handle.path().document_dir().unwrap_or_else(|_| {
        // Fallback para sistemas que no soporten document_dir
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

/// Crea la estructura de directorios para un módulo dado
pub fn ensure_arca_dirs(base_dir: &Path, year: &str, month: &str) -> Result<PathBuf, String> {
    let mut path = base_dir.to_path_buf();
    path.push(year);
    path.push(month);
    fs::create_dir_all(&path).map_err(|e| format!("Error creando directorios: {}", e))?;
    Ok(path)
}

/// Helper para ubicar el directorio principal de datos usando el AppHandle
pub fn get_base_data_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    path.push("data");
    path
}

pub fn get_backups_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = get_base_data_dir(app_handle);
    path.push(".backups");
    path
}

/// Extrae DDMMYYYY desde un string "YYYY-MM-DD" o asume DDMMYYYY si no lo es
pub fn format_date_for_filename(fecha: &str) -> String {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        // YYYY, MM, DD -> DDMMYYYY
        format!("{}{}{}", parts[2], parts[1], parts[0])
    } else {
        fecha.replace("-", "")
    }
}

/// Extrae (year, month) desde un string "YYYY-MM-DD" o DDMMYYYY
pub fn parse_date_parts(fecha: &str) -> (String, String) {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        (parts[0].to_string(), parts[1].to_string())
    } else if fecha.len() == 8 {
        (fecha[4..8].to_string(), fecha[2..4].to_string())
    } else {
        ("2025".to_string(), "12".to_string())
    }
}

pub fn validate_inputs(station_code: &str, fecha: &str) -> Result<(), String> {
    if station_code.is_empty() || station_code.len() > 10 {
        return Err("Código de estación inválido".to_string());
    }
    if !station_code.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
        return Err("Código de estación contiene caracteres no permitidos".to_string());
    }

    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        let yyyy = parts[0];
        let mm = parts[1];
        let dd = parts[2];
        if yyyy.len() != 4 || mm.len() != 2 || dd.len() != 2 {
            return Err("Formato de fecha inválido. Se espera YYYY-MM-DD".to_string());
        }
        if !yyyy.chars().all(|c| c.is_ascii_digit())
            || !mm.chars().all(|c| c.is_ascii_digit())
            || !dd.chars().all(|c| c.is_ascii_digit())
        {
            return Err("La fecha debe contener solo dígitos".to_string());
        }
    } else if fecha.len() == 8 {
        if !fecha.chars().all(|c| c.is_ascii_digit()) {
            return Err("La fecha debe contener solo dígitos".to_string());
        }
    } else {
        return Err("Formato de fecha inválido".to_string());
    }

    Ok(())
}

/// Helper para crear un backup manteniendo máximo los últimos 10 de esa estación
pub fn create_backup(filepath: &Path, station_code: &str, app_handle: &AppHandle) -> Option<String> {
    if !filepath.exists() {
        return None;
    }

    let backup_dir = get_backups_dir(app_handle).join(station_code);
    if !backup_dir.exists() {
        let _ = fs::create_dir_all(&backup_dir);
    }

    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();
    let filename = filepath
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("backup");
    let backup_name = format!("{}.{}.bak", filename, timestamp);
    let backup_path = backup_dir.join(&backup_name);

    if fs::copy(filepath, &backup_path).is_ok() {
        // Clean old backups
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
            backups.sort_by(|a, b| b.0.cmp(&a.0)); // Reverso (nuevos primero)
            for old in backups.iter().skip(10) {
                let _ = fs::remove_file(&old.1);
            }
        }
        return Some(backup_path.to_string_lossy().to_string());
    }

    None
}
