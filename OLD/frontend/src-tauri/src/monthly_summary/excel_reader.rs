use calamine::{open_workbook_auto, Data, Reader};
use std::path::Path;

use super::config::ExcelConfig;
use super::json_pipeline::{
    DailyObservation, DaySummary, HourlyData, HourlyRecord, ObservationMeta,
};

fn extract_date_from_filename(path: &Path) -> Option<String> {
    let file_stem = path.file_stem()?.to_str()?;
    // Regex for 8 digits DDMMYYYY
    let re = regex::Regex::new(r"(\d{8})").ok()?;
    if let Some(caps) = re.captures(file_stem) {
        return Some(caps[1].to_string());
    }
    None
}

fn extract_station_from_filename(path: &Path) -> String {
    let file_stem = path.file_stem().unwrap_or_default().to_str().unwrap_or_default();
    let re = regex::Regex::new(r"^(.*?)(?:\s*\d{8})").unwrap();
    if let Some(caps) = re.captures(file_stem) {
        let st = caps[1].trim().to_string();
        if !st.is_empty() {
            return st;
        }
    }
    "Estacion".to_string()
}

fn get_f64(cell: &Data) -> Option<f64> {
    match cell {
        Data::Float(f) => Some(*f),
        Data::Int(i) => Some(*i as f64),
        Data::String(s) => s.parse::<f64>().ok(),
        _ => None,
    }
}

pub fn build_observation_from_excel(path: &Path, config: &ExcelConfig) -> Result<DailyObservation, String> {
    let mut workbook = open_workbook_auto(path).map_err(|e| format!("Failed to open excel: {}", e))?;
    
    // Read sheets
    let mut get_sheet = |name: &str| -> Result<calamine::Range<Data>, String> {
        let range_result = workbook.worksheet_range(name);
        match range_result {
            Ok(range) => Ok(range),
            Err(e) => Err(format!("Error reading sheet {}: {}", name, e)),
        }
    };
    
    let sheet_3074 = get_sheet(config.sheet_daily)?;
    let sheet_4074 = get_sheet(config.sheet_cloud_temp).unwrap_or_else(|_| calamine::Range::empty());
    let sheet_1200z = get_sheet(config.sheet_rain).unwrap_or_else(|_| calamine::Range::empty());
    
    // Extract metadata
    let fecha = extract_date_from_filename(path).unwrap_or_else(|| "01011970".to_string());
    
    // Try to get station from B3 (row 2, col 1 in 0-indexed) or fallback to filename
    let mut estacion = extract_station_from_filename(path);
    if let Some(Data::String(s)) = sheet_3074.get_value((2, 1)) {
        if !s.trim().is_empty() {
            estacion = s.trim().to_string();
        }
    }

    let meta = ObservationMeta { estacion, fecha };
    
    let hours_map = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"];
    
    let mut horarias = Vec::new();
    
    for (i, &row_idx) in config.rows_8_observations.iter().enumerate() {
        let p_est = sheet_3074.get_value((row_idx as u32, config.col_presion_estacion as u32)).and_then(get_f64);
        let p_nmm = sheet_3074.get_value((row_idx as u32, config.col_presion_nmm as u32)).and_then(get_f64);
        let rocio = sheet_3074.get_value((row_idx as u32, config.col_punto_rocio as u32)).and_then(get_f64);
        let t_vapor = sheet_3074.get_value((row_idx as u32, config.col_tension_vapor as u32)).and_then(get_f64);
        let hr = sheet_3074.get_value((row_idx as u32, config.col_humedad_relativa as u32)).and_then(get_f64);
        let v_dir_deg = sheet_3074.get_value((row_idx as u32, config.col_viento_direccion as u32)).and_then(get_f64);
        let v_vel = sheet_3074.get_value((row_idx as u32, config.col_viento_velocidad as u32)).and_then(get_f64);
        
        let hr_rec = HourlyRecord {
            hora: hours_map[i].to_string(),
            datos: HourlyData {
                p_est, p_nmm, rocio, t_vapor, hr, v_dir_deg, v_vel,
                tmax: None, tmin: None, nub: None,
            }
        };
        horarias.push(hr_rec);
    }
    
    // TMAX
    for &row_idx in &config.rows_4_temperatures {
        let tmax = sheet_4074.get_value((row_idx as u32, config.col_temp_maxima as u32)).and_then(get_f64);
        if tmax.is_some() {
            horarias.push(HourlyRecord {
                hora: "TMAX".to_string(),
                datos: HourlyData { tmax, p_est: None, p_nmm: None, rocio: None, t_vapor: None, hr: None, v_dir_deg: None, v_vel: None, tmin: None, nub: None }
            });
        }
    }
    
    // TMIN
    for &row_idx in &config.rows_4_temperatures {
        let tmin = sheet_4074.get_value((row_idx as u32, config.col_temp_minima as u32)).and_then(get_f64);
        if tmin.is_some() {
            horarias.push(HourlyRecord {
                hora: "TMIN".to_string(),
                datos: HourlyData { tmin, p_est: None, p_nmm: None, rocio: None, t_vapor: None, hr: None, v_dir_deg: None, v_vel: None, tmax: None, nub: None }
            });
        }
    }
    
    // Nubosidad Dia
    for &row_idx in &config.rows_cloud_day {
        let nub = sheet_4074.get_value((row_idx as u32, config.col_nuvosidad as u32)).and_then(get_f64);
        if nub.is_some() {
            horarias.push(HourlyRecord {
                hora: "filas_nuvosidad_dia".to_string(),
                datos: HourlyData { nub, p_est: None, p_nmm: None, rocio: None, t_vapor: None, hr: None, v_dir_deg: None, v_vel: None, tmax: None, tmin: None }
            });
        }
    }
    
    // Nubosidad Tarde
    for &row_idx in &config.rows_cloud_afternoon {
        let nub = sheet_4074.get_value((row_idx as u32, config.col_nuvosidad as u32)).and_then(get_f64);
        if nub.is_some() {
            horarias.push(HourlyRecord {
                hora: "filas_nuvosidad_tarde".to_string(),
                datos: HourlyData { nub, p_est: None, p_nmm: None, rocio: None, t_vapor: None, hr: None, v_dir_deg: None, v_vel: None, tmax: None, tmin: None }
            });
        }
    }
    
    // Lluvia
    let pp = sheet_1200z.get_value((config.rain_cell.0, config.rain_cell.1)).and_then(get_f64);
    
    Ok(DailyObservation {
        meta,
        horarias,
        resumen_dia: DaySummary { pp },
    })
}

