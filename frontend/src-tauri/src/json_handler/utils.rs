// ponytail: single owner is infrastructure::storage; re-export for backward compat
pub use crate::infrastructure::storage::{
    arca_base_dir, atomic_write, create_backup, ensure_arca_dirs,
    ensure_arca_dirs_with_station, ensure_station_dir, get_arca_base_dir, get_backups_dir,
    get_base_data_dir, station_dir, SYNOP_MODULE,
};

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

