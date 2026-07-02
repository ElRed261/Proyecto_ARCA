use tauri::{command, AppHandle, Manager};
use std::path::{Path, PathBuf};

use super::json_pipeline::{
    analyze_files, export_to_excel, list_summary_history, load_summary, save_summary,
    MonthlySummaryDoc, SummaryIndexEntry,
};

fn get_monthly_summary_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let docs_dir = app
        .path()
        .document_dir()
        .map_err(|_| "No se pudo obtener la carpeta de documentos".to_string())?;
    
    Ok(docs_dir.join("Proyecto_ARCA").join("Resumen_Mensual_Synop"))
}

fn validate_safe_path(app: &AppHandle, path_str: &str) -> Result<PathBuf, String> {
    let base_dir = get_monthly_summary_dir(app)?;
    let target_path = Path::new(path_str);
    
    let canonical_path = if target_path.exists() {
        target_path.canonicalize().map_err(|e| format!("Error de ruta: {}", e))?
    } else {
        let parent = target_path.parent().ok_or("Ruta sin directorio padre")?;
        if parent.exists() {
            let canonical_parent = parent.canonicalize().map_err(|e| format!("Error de ruta: {}", e))?;
            let file_name = target_path.file_name().ok_or("Nombre de archivo inválido")?;
            canonical_parent.join(file_name)
        } else {
            return Err("El directorio de destino no existe".to_string());
        }
    };

    let canonical_base = base_dir.canonicalize().unwrap_or(base_dir);
    if !canonical_path.starts_with(&canonical_base) {
        return Err("Acceso no autorizado: la ruta está fuera del directorio permitido".to_string());
    }

    Ok(canonical_path)
}

fn validate_export_path(app: &AppHandle, path_str: &str) -> Result<PathBuf, String> {
    let target_path = Path::new(path_str);
    
    let extension = target_path.extension()
        .and_then(|ext| ext.to_str())
        .ok_or_else(|| "El archivo de destino debe tener una extensión válida".to_string())?
        .to_lowercase();
        
    if extension != "xlsx" && extension != "xls" {
        return Err("Extensión de archivo no permitida. Solo se admite .xlsx".to_string());
    }

    if path_str.contains("..") {
        return Err("Ruta inválida: no se permiten rutas relativas".to_string());
    }

    let docs = app.path().document_dir().ok();
    let downloads = app.path().download_dir().ok();
    let desktop = app.path().desktop_dir().ok();
    
    let path_abs = if target_path.is_absolute() {
        target_path.to_path_buf()
    } else {
        return Err("Se requiere una ruta absoluta para exportar".to_string());
    };

    let mut is_safe = false;
    for safe_dir in [docs, downloads, desktop].into_iter().flatten() {
        if let Ok(safe_base) = safe_dir.canonicalize() {
            if path_abs.starts_with(&safe_base) {
                is_safe = true;
                break;
            }
        }
    }

    if !is_safe {
        return Err("Acceso no autorizado: solo se permite exportar a Documentos, Descargas o Escritorio".to_string());
    }

    Ok(path_abs)
}

#[command]
pub async fn ms_generate_summary(app: AppHandle, files: Vec<String>) -> Result<MonthlySummaryDoc, String> {
    let doc = analyze_files(files)?;
    
    let dir = get_monthly_summary_dir(&app)?;
    save_summary(&doc, &dir)?;
    
    Ok(doc)
}

#[command]
pub async fn ms_list_history(app: AppHandle) -> Result<Vec<SummaryIndexEntry>, String> {
    let dir = get_monthly_summary_dir(&app)?;
    let mut history = list_summary_history(&dir)?;
    
    // Sort by generated date conceptually (here we just reverse sort by period)
    history.sort_by(|a, b| b.period.cmp(&a.period));
    Ok(history)
}

#[command]
pub async fn ms_load_summary(app: AppHandle, path: String) -> Result<MonthlySummaryDoc, String> {
    let safe_path = validate_safe_path(&app, &path)?;
    load_summary(&safe_path)
}

#[command]
pub async fn ms_export_excel(app: AppHandle, doc: MonthlySummaryDoc, out_path: String) -> Result<String, String> {
    let safe_path = validate_export_path(&app, &out_path)?;
    export_to_excel(&doc, &safe_path)?;
    Ok(safe_path.to_string_lossy().to_string())
}

#[command]
pub async fn ms_load_station_month(
    app: AppHandle,
    station_code: String,
    year: u32,
    month: u32,
) -> Result<MonthlySummaryDoc, String> {
    // 1. Get documents directory
    let docs_dir = app
        .path()
        .document_dir()
        .map_err(|_| "No se pudo obtener la carpeta de documentos".to_string())?;
    
    let month_str = format!("{:02}", month);
    let year_str = year.to_string();
    let synop_dir = docs_dir
        .join("ARCA")
        .join("synop")
        .join(&station_code)
        .join(&year_str)
        .join(&month_str);
    
    if !synop_dir.exists() {
        return Err(format!(
            "No se encontraron datos para la estación {} en el periodo {:02}/{}",
            station_code, month, year
        ));
    }
    
    // 2. Find all json files in that directory
    let mut paths = Vec::new();
    for entry in (std::fs::read_dir(&synop_dir).map_err(|e| e.to_string())?).flatten() {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("json") {
            paths.push(path.to_string_lossy().to_string());
        }
    }
    
    if paths.is_empty() {
        return Err(format!(
            "No se encontraron archivos JSON en la carpeta {:?}",
            synop_dir
        ));
    }
    
    // 3. Analyze and automatically adapt files
    let doc = analyze_files(paths)?;
    
    // 4. Save to summary history directory
    let dir = get_monthly_summary_dir(&app)?;
    save_summary(&doc, &dir)?;
    
    Ok(doc)
}

#[command]
pub async fn ms_load_station_month_with_corrections(
    app: AppHandle,
    station_code: String,
    year: u32,
    month: u32,
) -> Result<MonthlySummaryDoc, String> {
    // 1. Get documents directory
    let docs_dir = app
        .path()
        .document_dir()
        .map_err(|_| "No se pudo obtener la carpeta de documentos".to_string())?;
    
    let month_str = format!("{:02}", month);
    let year_str = year.to_string();
    let synop_dir = docs_dir
        .join("ARCA")
        .join("synop")
        .join(&station_code)
        .join(&year_str)
        .join(&month_str);
    
    if !synop_dir.exists() {
        return Err(format!(
            "No se encontraron datos para la estación {} en el periodo {:02}/{}",
            station_code, month, year
        ));
    }
    
    // 2. Find files, prioritizing corrected ones
    let corr_dir = synop_dir.join("correcciones");
    let mut paths = Vec::new();
    
    for entry in (std::fs::read_dir(&synop_dir).map_err(|e| e.to_string())?).flatten() {
        let path = entry.path();
        if path.is_file() && path.extension().and_then(|s| s.to_str()) == Some("json") {
            if let Some(file_name) = path.file_stem().and_then(|s| s.to_str()) {
                let corr_file_name = format!("{}_cor.json", file_name);
                let corr_path = corr_dir.join(&corr_file_name);
                
                if corr_path.exists() {
                    paths.push(corr_path.to_string_lossy().to_string());
                } else {
                    paths.push(path.to_string_lossy().to_string());
                }
            }
        }
    }
    
    if paths.is_empty() {
        return Err(format!(
            "No se encontraron archivos JSON en la carpeta {:?}",
            synop_dir
        ));
    }
    
    // 3. Analyze and automatically adapt files
    let mut doc = analyze_files(paths)?;
    
    // 4. Mark generated date metadata with suffix
    doc.meta.generado = format!("{} (con correcciones)", doc.meta.generado);
    
    // 5. Save to summary history directory
    let dir = get_monthly_summary_dir(&app)?;
    save_summary(&doc, &dir)?;
    
    Ok(doc)
}

#[command]
pub async fn ms_delete_summary(app: AppHandle, path: String) -> Result<(), String> {
    let safe_path = validate_safe_path(&app, &path)?;
    trash::delete(&safe_path).map_err(|e| e.to_string())
}
