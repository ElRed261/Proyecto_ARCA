use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::fs;
use rust_xlsxwriter::{Workbook, Format};

use super::calculations::process_day_data;
use super::excel_reader::build_observation_from_excel;
use super::config::get_default_config;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ObservationMeta {
    pub estacion: String,
    pub fecha: String, // DDMMYYYY
}

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct HourlyData {
    pub p_est: Option<f64>,
    pub p_nmm: Option<f64>,
    pub rocio: Option<f64>,
    pub t_vapor: Option<f64>,
    pub hr: Option<f64>,
    pub v_dir_deg: Option<f64>,
    pub v_vel: Option<f64>,
    
    // Extended fields that might be missing in basic JSON schema
    pub tmax: Option<f64>,
    pub tmin: Option<f64>,
    pub nub: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct HourlyRecord {
    pub hora: String,
    pub datos: HourlyData,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct DaySummary {
    pub pp: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct DailyObservation {
    pub meta: ObservationMeta,
    pub horarias: Vec<HourlyRecord>,
    pub resumen_dia: DaySummary,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct DailyKpis {
    #[serde(rename = "Dias")]
    pub dias: String, // YYYY-MM-DD
    
    #[serde(rename = "Mayor temperatura máxima")]
    pub t_max: Option<f64>,
    #[serde(rename = "Menor temperatura minima")]
    pub t_min: Option<f64>,
    #[serde(rename = "Media temperatura")]
    pub t_media: Option<f64>,
    
    #[serde(rename = "MAxima presión nivel medio del mar")]
    pub p_nmm_max: Option<f64>,
    #[serde(rename = "Minima presión nivel medio del mar")]
    pub p_nmm_min: Option<f64>,
    #[serde(rename = "Media presión nivel medio del mar")]
    pub p_nmm_media: Option<f64>,
    
    #[serde(rename = "Media presion en la estación")]
    pub p_est_media: Option<f64>,
    
    #[serde(rename = "Lluvia")]
    pub lluvia: Option<f64>,
    
    #[serde(rename = "Dirección del viento")]
    pub viento_dir_moda: Option<String>,
    #[serde(rename = "Velocidad media del viento")]
    pub viento_vel_media: Option<f64>,
    #[serde(rename = "Velocidad máxima y direccion")]
    pub viento_max_dir: Option<String>,
    #[serde(rename = "Recorrido del viento")]
    pub viento_recorrido: Option<f64>,
    
    #[serde(rename = "Nuvocidad dia")]
    pub nub_dia_media: Option<f64>,
    #[serde(rename = "Nuvocidad noche")]
    pub nub_tarde_media: Option<f64>,
    #[serde(rename = "Media de nuvocidad")]
    pub nub_media: Option<f64>,
    
    #[serde(rename = "Humedad maxima")]
    pub hr_max: Option<f64>,
    #[serde(rename = "Humedad minima")]
    pub hr_min: Option<f64>,
    #[serde(rename = "Humedad media")]
    pub hr_media: Option<f64>,
    
    #[serde(rename = "Punto de rocio")]
    pub rocio_media: Option<f64>,
    #[serde(rename = "Tensión de vapor")]
    pub t_vapor_media: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct SummaryMeta {
    pub estacion: String,
    pub periodo: String, // MM/YYYY
    pub total_dias: usize,
    pub generado: String,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MonthlySummaryDoc {
    pub meta: SummaryMeta,
    pub datos: Vec<DailyKpis>,
}

// -----------------------------------------------------------------------------
// Orchestration & Persistence
// -----------------------------------------------------------------------------

pub fn analyze_files(paths: Vec<String>) -> Result<MonthlySummaryDoc, String> {
    let config = get_default_config();
    let mut observations = Vec::new();

    // 1. Load all observations
    for p in &paths {
        let path = Path::new(p);
        let obs = if p.to_lowercase().ends_with(".json") {
            let content = fs::read_to_string(path).map_err(|e| format!("Failed to read {}: {}", p, e))?;
            let val: serde_json::Value = serde_json::from_str(&content).map_err(|e| format!("Failed to parse JSON {}: {}", p, e))?;
            
            if val.get("horas").is_some() {
                super::synop_adapter::adapt_synoptic_json(val).map_err(|e| format!("Failed to adapt synoptic JSON {}: {}", p, e))?
            } else {
                serde_json::from_value::<DailyObservation>(val).map_err(|e| format!("Failed to parse DailyObservation from JSON {}: {}", p, e))?
            }
        } else {
            build_observation_from_excel(path, &config).map_err(|e| format!("Failed to read excel {}: {}", p, e))?
        };
        observations.push(obs);
    }

    if observations.is_empty() {
        return Err("No valid files to analyze".to_string());
    }

    // 2. Sort by date (DDMMYYYY)
    observations.sort_by(|a, b| {
        let date_a = format!("{}{}{}", &a.meta.fecha[4..], &a.meta.fecha[2..4], &a.meta.fecha[0..2]);
        let date_b = format!("{}{}{}", &b.meta.fecha[4..], &b.meta.fecha[2..4], &b.meta.fecha[0..2]);
        date_a.cmp(&date_b)
    });

    // 3. Process into KPIs and handle rainfall shifting (rain recorded today belongs to yesterday)
    let mut kpis_list = Vec::new();
    let mut next_day_rain: Option<f64> = None;

    // We process in reverse to shift rain from day N to day N-1
    for obs in observations.iter().rev() {
        let mut kpis = process_day_data(obs);
        kpis.lluvia = next_day_rain;
        next_day_rain = obs.resumen_dia.pp;
        kpis_list.push(kpis);
    }
    
    // Reverse again to chronological order
    kpis_list.reverse();

    // 4. Build Document
    let estacion = observations.first().unwrap().meta.estacion.clone();
    let periodo = if let Some(first_obs) = observations.first() {
        if first_obs.meta.fecha.len() == 8 {
            format!("{}/{}", &first_obs.meta.fecha[2..4], &first_obs.meta.fecha[4..8])
        } else {
            "S/F".to_string()
        }
    } else {
        "S/F".to_string()
    };

    let doc = MonthlySummaryDoc {
        meta: SummaryMeta {
            estacion,
            periodo,
            total_dias: kpis_list.len(),
            generado: chrono::Local::now().to_rfc3339(),
        },
        datos: kpis_list,
    };

    Ok(doc)
}

pub fn save_summary(doc: &MonthlySummaryDoc, dir: &Path) -> Result<PathBuf, String> {
    fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    
    let safe_station = doc.meta.estacion.replace('/', "_").replace('\\', "_");
    let safe_period = doc.meta.periodo.replace('/', "");
    let filename = format!("resumen_{}_{}.json", safe_station, safe_period);
    
    let path = dir.join(filename);
    let json_str = serde_json::to_string_pretty(doc).map_err(|e| e.to_string())?;
    fs::write(&path, json_str).map_err(|e| e.to_string())?;
    
    Ok(path)
}

pub fn load_summary(path: &Path) -> Result<MonthlySummaryDoc, String> {
    let content = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let doc: MonthlySummaryDoc = serde_json::from_str(&content).map_err(|e| e.to_string())?;
    Ok(doc)
}

#[derive(Serialize, Deserialize)]
pub struct SummaryIndexEntry {
    pub station: String,
    pub period: String,
    pub path: String,
}

pub fn list_summary_history(dir: &Path) -> Result<Vec<SummaryIndexEntry>, String> {
    let mut entries = Vec::new();
    if !dir.exists() {
        return Ok(entries);
    }
    
    for entry in fs::read_dir(dir).map_err(|e| e.to_string())? {
        if let Ok(entry) = entry {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("json") {
                if let Ok(content) = fs::read_to_string(&path) {
                    if let Ok(meta_doc) = serde_json::from_str::<serde_json::Value>(&content) {
                        if let Some(meta) = meta_doc.get("meta") {
                            let station = meta.get("estacion").and_then(|v| v.as_str()).unwrap_or("Desconocida").to_string();
                            let period = meta.get("periodo").and_then(|v| v.as_str()).unwrap_or("S/F").to_string();
                            entries.push(SummaryIndexEntry {
                                station,
                                period,
                                path: path.to_string_lossy().to_string(),
                            });
                        }
                    }
                }
            }
        }
    }
    Ok(entries)
}

// -----------------------------------------------------------------------------
// Excel Export
// -----------------------------------------------------------------------------
pub fn export_to_excel(doc: &MonthlySummaryDoc, out_path: &Path) -> Result<(), String> {
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();
    
    let headers = [
        "Dias", "Mayor temperatura máxima", "Menor temperatura minima", "Media temperatura",
        "MAxima presión nivel medio del mar", "Minima presión nivel medio del mar", "Media presión nivel medio del mar",
        "Media presion en la estación", "Lluvia", "Dirección del viento", "Velocidad media del viento",
        "Velocidad máxima y direccion", "Recorrido del viento", "Nuvocidad dia", "Nuvocidad noche", "Media de nuvocidad",
        "Humedad maxima", "Humedad minima", "Humedad media", "Punto de rocio", "Tensión de vapor"
    ];
    
    let format_header = Format::new().set_bold();
    for (i, header) in headers.iter().enumerate() {
        worksheet.write_string_with_format(0, i as u16, *header, &format_header).unwrap();
    }
    
    for (r, row) in doc.datos.iter().enumerate() {
        let row_idx = (r + 1) as u32;
        worksheet.write_string(row_idx, 0, &row.dias).unwrap();
        
        if let Some(v) = row.t_max { worksheet.write_number(row_idx, 1, v).unwrap(); }
        if let Some(v) = row.t_min { worksheet.write_number(row_idx, 2, v).unwrap(); }
        if let Some(v) = row.t_media { worksheet.write_number(row_idx, 3, v).unwrap(); }
        if let Some(v) = row.p_nmm_max { worksheet.write_number(row_idx, 4, v).unwrap(); }
        if let Some(v) = row.p_nmm_min { worksheet.write_number(row_idx, 5, v).unwrap(); }
        if let Some(v) = row.p_nmm_media { worksheet.write_number(row_idx, 6, v).unwrap(); }
        if let Some(v) = row.p_est_media { worksheet.write_number(row_idx, 7, v).unwrap(); }
        if let Some(v) = row.lluvia { worksheet.write_number(row_idx, 8, v).unwrap(); }
        if let Some(ref v) = row.viento_dir_moda { worksheet.write_string(row_idx, 9, v).unwrap(); }
        if let Some(v) = row.viento_vel_media { worksheet.write_number(row_idx, 10, v).unwrap(); }
        if let Some(ref v) = row.viento_max_dir { worksheet.write_string(row_idx, 11, v).unwrap(); }
        if let Some(v) = row.viento_recorrido { worksheet.write_number(row_idx, 12, v).unwrap(); }
        if let Some(v) = row.nub_dia_media { worksheet.write_number(row_idx, 13, v).unwrap(); }
        if let Some(v) = row.nub_tarde_media { worksheet.write_number(row_idx, 14, v).unwrap(); }
        if let Some(v) = row.nub_media { worksheet.write_number(row_idx, 15, v).unwrap(); }
        if let Some(v) = row.hr_max { worksheet.write_number(row_idx, 16, v).unwrap(); }
        if let Some(v) = row.hr_min { worksheet.write_number(row_idx, 17, v).unwrap(); }
        if let Some(v) = row.hr_media { worksheet.write_number(row_idx, 18, v).unwrap(); }
        if let Some(v) = row.rocio_media { worksheet.write_number(row_idx, 19, v).unwrap(); }
        if let Some(v) = row.t_vapor_media { worksheet.write_number(row_idx, 20, v).unwrap(); }
    }
    
    workbook.save(out_path).map_err(|e| format!("Failed to save excel: {}", e))?;
    Ok(())
}
