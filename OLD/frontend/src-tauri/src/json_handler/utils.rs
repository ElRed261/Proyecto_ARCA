// ponytail: single owner is infrastructure::storage; re-export for backward compat
pub use crate::infrastructure::storage::{
    atomic_write, create_backup, ensure_arca_dirs,
    ensure_arca_dirs_with_station, ensure_station_dir, get_backups_dir,
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

/// Extrae (year, month) desde "YYYY-MM-DD" o DDMMYYYY.
/// P1.4 — HARD-FAIL: una fecha malformada/fuera de rango da ERROR; nunca más
/// un default silencioso (antes caía a ("2025","12") y se leía el path mal).
pub fn parse_date_parts(fecha: &str) -> Result<(String, String), String> {
    let (year, month, day) = if let Some((y, m, d)) = split_iso(fecha) {
        (y, m, d)
    } else if fecha.len() == 8 {
        (fecha[4..8].to_string(), fecha[2..4].to_string(), fecha[0..2].to_string())
    } else {
        return Err(format!(
            "Formato de fecha inválido: '{}' no es YYYY-MM-DD ni DDMMYYYY",
            fecha
        ));
    };

    if !year.chars().all(|c| c.is_ascii_digit())
        || !month.chars().all(|c| c.is_ascii_digit())
        || !day.chars().all(|c| c.is_ascii_digit())
    {
        return Err(format!("La fecha '{}' debe contener solo dígitos", fecha));
    }

    let y: i32 = year.parse().map_err(|_| format!("Año inválido en '{}'", fecha))?;
    let m: u32 = month.parse().map_err(|_| format!("Mes inválido en '{}'", fecha))?;
    let d: u32 = day.parse().map_err(|_| format!("Día inválido en '{}'", fecha))?;

    if !(1990..=2250).contains(&y) {
        return Err(format!("Año '{}' fuera de rango razonable (1990-2250)", year));
    }
    if !(1..=12).contains(&m) {
        return Err(format!("mes '{}' inválido (debe ser 01-12)", month));
    }
    if !(1..=dias_del_mes(y, m)).contains(&d) {
        return Err(format!(
            "día '{}' inválido para {}-{}",
            day, year, month
        ));
    }

    Ok((year, month))
}

fn split_iso(fecha: &str) -> Option<(String, String, String)> {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        Some((parts[0].to_string(), parts[1].to_string(), parts[2].to_string()))
    } else {
        None
    }
}

fn dias_del_mes(year: i32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            // bisiesto gregoriano estándar
            let es_bisiesto = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
            if es_bisiesto {
                29
            } else {
                28
            }
        }
        _ => 0,
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


#[cfg(test)]
mod date_tests {
    use super::*;
    #[test]
    fn parse_acepta_yyyy_mm_dd() {
        let (year, month) = parse_date_parts("2026-04-15").expect("fecha válida");
        assert_eq!((year.as_str(), month.as_str()), ("2026", "04"));
    }
    #[test]
    fn parse_acepta_ddmm_yyyy() {
        let (year, month) = parse_date_parts("15042026").expect("fecha válida");
        assert_eq!((year.as_str(), month.as_str()), ("2026", "04"));
    }
    #[test]
    fn parse_rechaza_basura() {
        let err = parse_date_parts("nada").expect_err("basura debe fallar");
        assert!(err.contains("inválid"), "fue: {}", err);
    }
    #[test]
    fn parse_rechaza_mes_fuera_de_rango() {
        let err = parse_date_parts("2026-99-15").expect_err("mes 99 debe fallar");
        assert!(
            err.contains("mes") ,
            "el error debe explicar el mes inválido, fue: {}",
            err
        );
    }
    #[test]
    fn parse_rechaza_dia_cero() {
        let err = parse_date_parts("2026-04-00").expect_err("día 00 debe fallar");
        assert!(err.contains("día"), "el error debe explicar el día inválido, fue: {}", err);
    }
    #[test]
    fn parse_acepta_dia_31() {
        let (_y, _m) = parse_date_parts("2026-01-31").expect("día 31 es real");
    }
    #[test]
    fn parse_acepta_feb_29_solo_si_bisiesto_de_lo_contrario_rechaza() {
        // 2024 bisiesto → válido
        parse_date_parts("2024-02-29").expect("2024 es bisiesto");
        // 2026 no bisiesto → 29/02 debe fallar
        let err = parse_date_parts("2026-02-29")
            .expect_err("2026 no es bisiesto: 29/02 no existe");
        assert!(err.contains("día"), "fue: {}", err);
    }
    #[test]
    fn format_conserva_ddmm_yy_dd() {
        assert_eq!(format_date_for_filename("2026-04-15"), "15042026");
        assert_eq!(format_date_for_filename("15042026"), "15042026");
    }
}
