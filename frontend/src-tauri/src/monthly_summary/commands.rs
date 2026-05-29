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
    
    // Sort by generated date conceptually (here we just reverse sort by period ideally)
    history.sort_by(|a, b| b.period.cmp(&a.period));
    Ok(history)
}

#[command]
pub async fn ms_load_summary(path: String) -> Result<MonthlySummaryDoc, String> {
    load_summary(Path::new(&path))
}

#[command]
pub async fn ms_export_excel(_app: AppHandle, doc: MonthlySummaryDoc, out_path: String) -> Result<String, String> {
    export_to_excel(&doc, Path::new(&out_path))?;
    Ok(out_path)
}

