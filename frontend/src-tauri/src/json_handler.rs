use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

// =============================================================================
// RUTAS MULTIPLATAFORMA - Documents/OBSERVACIONES/ARCA/{MODULO}/YYYY/MM/
// =============================================================================

/// Obtiene el directorio base de Documents/ARCA/{modulo}/
/// Funciona en Windows, macOS y Linux
fn get_arca_base_dir(app_handle: &AppHandle, modulo: &str) -> PathBuf {
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
fn ensure_arca_dirs(base_dir: &Path, year: &str, month: &str) -> Result<PathBuf, String> {
    let mut path = base_dir.to_path_buf();
    path.push(year);
    path.push(month);
    fs::create_dir_all(&path).map_err(|e| format!("Error creando directorios: {}", e))?;
    Ok(path)
}

/// Helper para ubicar el directorio principal de datos usando el AppHandle
fn get_base_data_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = app_handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| PathBuf::from("."));
    path.push("data");
    path
}

fn get_backups_dir(app_handle: &AppHandle) -> PathBuf {
    let mut path = get_base_data_dir(app_handle);
    path.push(".backups");
    path
}

/// Extrae DDMMYYYY desde un string "YYYY-MM-DD" o asume DDMMYYYY si no lo es
fn format_date_for_filename(fecha: &str) -> String {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        // YYYY, MM, DD -> DDMMYYYY
        format!("{}{}{}", parts[2], parts[1], parts[0])
    } else {
        fecha.replace("-", "")
    }
}

/// Extrae (year, month) desde un string "YYYY-MM-DD" o DDMMYYYY
fn parse_date_parts(fecha: &str) -> (String, String) {
    let parts: Vec<&str> = fecha.split('-').collect();
    if parts.len() == 3 {
        (parts[0].to_string(), parts[1].to_string())
    } else if fecha.len() == 8 {
        (fecha[4..8].to_string(), fecha[2..4].to_string())
    } else {
        ("2025".to_string(), "12".to_string())
    }
}

/// Helper para crear un backup manteniendo máximo los últimos 10 de esa estación
fn create_backup(filepath: &Path, station_code: &str, app_handle: &AppHandle) -> Option<String> {
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

// =============================================================================
// COMANDOS DE TAURI
// =============================================================================

// Mapeo de campos del frontend a nombres SYNOP OMM
const FRONTEND_TO_SYNOP: &[(&str, &str)] = &[
    // Grupo 2
    ("meteo_2_1", "YYGGiw"),
    // Grupo 4
    ("meteo_4_irixhvv", "IrIXHVV"),
    ("meteo_4_1", "Nddff"),
    ("meteo_4_6", "7wwW1W2"),
    // Grupo 6
    ("meteo_6_0", "8NhCLCMCH"),
    ("meteo_6_2", "0CSDL DM DH"),
    ("meteo_6_3", "1snTxTxTx"),
    ("meteo_6_4", "2snTnTnTn"),
    ("meteo_6_5", "3Ejjj"),
    ("meteo_6_6", "5EEEjE"),
    // Grupo 8
    ("meteo_8_0", "5nFnFnFn"),
    ("meteo_8_1", "56DLDMDH"),
    ("meteo_8_3", "6RRRtr"),
    ("meteo_8_4", "7R24R24R24R24"),
    ("meteo_8_5", "8NsChshs_1"),
    ("meteo_8_6", "8NsChshs_2"),
    ("extra_8ns_1", "8NsChshs_3"),
    ("extra_8ns_2", "8NsChshs_4"),
    // Grupos 9sp (serie 10 a 16)
    ("meteo_10_0", "8NsChshs_5"),
    ("meteo_10_1", "8NsChshs_6"),
    ("meteo_10_2", "9spspsp_1"),
    ("meteo_10_3", "9spspsp_2"),
    ("meteo_10_4", "9spspsp_3"),
    ("meteo_10_5", "9spspsp_4"),
    ("meteo_10_6", "9spspsp_5"),
    ("meteo_12_0", "9spspsp_6"),
    ("meteo_12_1", "9spspsp_7"),
    ("meteo_12_2", "9spspsp_8"),
    ("meteo_12_3", "9spspsp_9"),
    ("meteo_12_4", "9spspsp_10"),
    ("meteo_12_5", "9spspsp_11"),
    ("meteo_12_6", "9spspsp_12"),
    ("meteo_14_0", "9spspsp_13"),
    ("meteo_14_1", "9spspsp_14"),
    ("meteo_14_2", "9spspsp_15"),
    ("meteo_14_3", "9spspsp_16"),
    ("meteo_14_4", "9spspsp_17"),
    ("meteo_14_5", "9spspsp_18"),
    ("meteo_14_6", "9spspsp_19"),
    ("meteo_16_0", "9spspsp_20"),
    ("meteo_16_1", "9spspsp_21"),
    ("meteo_16_2", "9spspsp_22"),
    ("meteo_16_3", "9spspsp_23"),
    ("meteo_16_4", "9spspsp_24"),
];

// Mapeo inverso SYNOP a frontend (para cargar)
const SYNOP_TO_FRONTEND: &[(&str, &str)] = &[
    ("YYGGiw", "meteo_2_1"),
    ("IrIXHVV", "meteo_4_irixhvv"),
    ("Nddff", "meteo_4_1"),
    ("7wwW1W2", "meteo_4_6"),
    ("8NhCLCMCH", "meteo_6_0"),
    ("0CSDL DM DH", "meteo_6_2"),
    ("1snTxTxTx", "meteo_6_3"),
    ("2snTnTnTn", "meteo_6_4"),
    ("3Ejjj", "meteo_6_5"),
    ("5EEEjE", "meteo_6_6"),
    ("5nFnFnFn", "meteo_8_0"),
    ("56DLDMDH", "meteo_8_1"),
    ("6RRRtr", "meteo_8_3"),
    ("7R24R24R24R24", "meteo_8_4"),
    ("8NsChshs_1", "meteo_8_5"),
    ("8NsChshs_2", "meteo_8_6"),
    ("8NsChshs_3", "extra_8ns_1"),
    ("8NsChshs_4", "extra_8ns_2"),
    ("8NsChshs_5", "meteo_10_0"),
    ("8NsChshs_6", "meteo_10_1"),
    ("9spspsp_1", "meteo_10_2"),
    ("9spspsp_2", "meteo_10_3"),
    ("9spspsp_3", "meteo_10_4"),
    ("9spspsp_4", "meteo_10_5"),
    ("9spspsp_5", "meteo_10_6"),
    ("9spspsp_6", "meteo_12_0"),
    ("9spspsp_7", "meteo_12_1"),
    ("9spspsp_8", "meteo_12_2"),
    ("9spspsp_9", "meteo_12_3"),
    ("9spspsp_10", "meteo_12_4"),
    ("9spspsp_11", "meteo_12_5"),
    ("9spspsp_12", "meteo_12_6"),
    ("9spspsp_13", "meteo_14_0"),
    ("9spspsp_14", "meteo_14_1"),
    ("9spspsp_15", "meteo_14_2"),
    ("9spspsp_16", "meteo_14_3"),
    ("9spspsp_17", "meteo_14_4"),
    ("9spspsp_18", "meteo_14_5"),
    ("9spspsp_19", "meteo_14_6"),
    ("9spspsp_20", "meteo_16_0"),
    ("9spspsp_21", "meteo_16_1"),
    ("9spspsp_22", "meteo_16_2"),
    ("9spspsp_23", "meteo_16_3"),
    ("9spspsp_24", "meteo_16_4"),
];

// Función helper para convertir nombre frontend a SYNOP
fn to_synop_name(frontend_name: &str) -> String {
    for (from, to) in FRONTEND_TO_SYNOP.iter() {
        if *from == frontend_name {
            return to.to_string();
        }
    }
    frontend_name.to_string()
}

// =============================================================================
// FUNCIONES DE CÁLCULO AUTOMÁTICO PARA CLI (usadas al cargar JSON)
// =============================================================================

// Map SYNOP names to frontend field names
fn to_frontend_name(synop_name: &str) -> String {
    let mapping = [
        ("YYGGiw", "meteo_2_1"),
        ("IrIXHVV", "meteo_4_irixhvv"),
        ("Nddff", "meteo_4_1"),
        ("7wwW1W2", "meteo_4_6"),
        ("8NhCLCMCH", "meteo_6_0"),
        ("0CSDL DM DH", "meteo_6_2"),
        ("1snTxTxTx", "meteo_6_3"),
        ("2snTnTnTn", "meteo_6_4"),
        ("3Ejjj", "meteo_6_5"),
        ("5EEEjE", "meteo_6_6"),
        ("5nFnFnFn", "meteo_8_0"),
        ("56DLDMDH", "meteo_8_1"),
        ("6RRRtr", "meteo_8_3"),
        ("7R24R24R24R24", "meteo_8_4"),
        ("8NsChshs_1", "meteo_8_5"),
        ("8NsChshs_2", "meteo_8_6"),
        ("8NsChshs_3", "extra_8ns_1"),
        ("8NsChshs_4", "extra_8ns_2"),
        ("8NsChshs_5", "meteo_10_0"),
        ("8NsChshs_6", "meteo_10_1"),
    ];
    for (s, f) in mapping.iter() {
        if *s == synop_name {
            return f.to_string();
        }
    }
    synop_name.to_string()
}

/// Tabla de conversión de visibilidad desde código VV (últimos 2 dígitos de IrIxHVV)
///
/// # Formato del grupo IrIxHVV:
/// - Ir: indicador de precipitación (1 dígito)
/// - Ix: indicador de tiempo (1 dígito)
/// - h: altura de la base de nubes (1 dígito)
/// - VV: visibilidad codificada (2 dígitos) ← este es el valor a convertir
///
/// # Ejemplos:
/// - Código "56" → valor "060" km
/// - Código "66" → valor "160" km
/// - Código "60" → valor "100" km
///
/// # Referencia:
/// WMO Manual on Codes, Code Table 4377 (Visibilidad)
fn get_visibilidad_from_irixhv(irixhv: &str) -> String {
    // Tabla literal de conversión código → valor
    let table: [(&str, &str); 75] = [
        ("00", "000"),
        ("01", "001"),
        ("02", "002"),
        ("03", "003"),
        ("04", "004"),
        ("05", "005"),
        ("06", "006"),
        ("07", "007"),
        ("08", "008"),
        ("09", "009"),
        ("10", "010"),
        ("11", "011"),
        ("12", "012"),
        ("13", "013"),
        ("14", "014"),
        ("15", "015"),
        ("16", "016"),
        ("17", "017"),
        ("18", "018"),
        ("19", "019"),
        ("20", "020"),
        ("21", "021"),
        ("22", "022"),
        ("23", "023"),
        ("24", "024"),
        ("25", "025"),
        ("26", "026"),
        ("27", "027"),
        ("28", "028"),
        ("29", "029"),
        ("30", "030"),
        ("31", "031"),
        ("32", "032"),
        ("33", "033"),
        ("34", "034"),
        ("35", "035"),
        ("36", "036"),
        ("37", "037"),
        ("38", "038"),
        ("39", "039"),
        ("40", "040"),
        ("41", "041"),
        ("42", "042"),
        ("43", "043"),
        ("44", "044"),
        ("45", "045"),
        ("46", "046"),
        ("47", "047"),
        ("48", "048"),
        ("49", "049"),
        ("56", "060"),
        ("57", "070"),
        ("58", "080"),
        ("59", "090"),
        ("60", "100"),
        ("61", "110"),
        ("62", "120"),
        ("63", "130"),
        ("64", "140"),
        ("65", "150"),
        ("66", "160"),
        ("67", "170"),
        ("68", "180"),
        ("69", "190"),
        ("70", "200"),
        ("71", "210"),
        ("72", "220"),
        ("73", "230"),
        ("74", "240"),
        ("75", "250"),
        ("76", "260"),
        ("77", "270"),
        ("78", "280"),
        ("79", "290"),
        ("80", "300"),
    ];
    // Extraer los últimos 2 dígitos (VV) del grupo IrIxHVV
    if irixhv.len() >= 2 {
        let code = &irixhv[irixhv.len() - 2..];
        for (k, v) in table.iter() {
            if *k == code {
                return v.to_string();
            }
        }
    }
    String::new()
}

/// Formatear DIF (diferencia de presión) al formato "00.0"
///
/// # Entrada esperada:
/// - 3 dígitos sin punto: "048" → "04.8"
/// - 4 dígitos sin punto: "0048" → "00.4" (raro, pero posible)
/// - Ya formateado: "04.8" → "04.8" (sin cambios)
///
/// # Referencia:
/// WMO Manual on Codes, grupo 5appp donde ppp es la tendencia
fn format_dif(dif_value: &str) -> String {
    if dif_value.is_empty() {
        return String::new();
    }
    // Si ya tiene formato correcto (XX.X), retornarlo sin cambios
    if dif_value.len() == 4 && dif_value.contains('.') {
        return dif_value.to_string();
    }
    // Si tiene 3 dígitos sin punto (ej: "048"), agregar punto: "04.8"
    if dif_value.len() == 3 {
        let chars: Vec<char> = dif_value.chars().collect();
        return format!("{}{}.{}", chars[0], chars[1], chars[2]);
    }
    // Si tiene 4 dígitos sin punto, formatear como XX.XX
    if dif_value.len() == 4 {
        let chars: Vec<char> = dif_value.chars().collect();
        return format!("{}{}.{}{}", chars[0], chars[1], chars[2], chars[3]);
    }
    dif_value.to_string()
}

/// Calcular DIF (diferencia de presión) desde presión de estación y P3
///
/// # Fórmula:
/// DIF = |pres_est - p3|
///
/// # Formato de salida:
/// "00.0" (4 caracteres con punto decimal)
fn calc_dif(pres_est: &str, p3: &str) -> String {
    // Intentar calcular desde valores numéricos
    if let (Ok(pe), Ok(p)) = (pres_est.parse::<f64>(), p3.parse::<f64>()) {
        let dif = (pe - p).abs();
        return format!("{:04.1}", dif);
    }
    String::new()
}

/// Calcular CAR (característica de la tendencia) desde la diferencia de presión
///
/// # Código WMO para el grupo 5appp:
/// - a = 0: Aumentó, luego disminuyó (ej: +0.1 a +0.5)
/// - a = 1: Aumentó, luego aumentó más (ej: +0.6 a +1.4)
/// - a = 2: Aumentó, luego estable (ej: +1.5 a +1.9)
/// - a = 3: Aumentó uniformemente (ej: ≥ +2.0)
/// - a = 4: Sin cambio (0.0)
/// - a = 5: Disminuyó, luego aumentó (ej: -0.1 a -0.5)
/// - a = 6: Disminuyó, luego disminuyó más (ej: -0.6 a -1.4)
/// - a = 7: Disminuyó, luego estable (ej: -1.5 a -1.9)
/// - a = 8: Disminuyó uniformemente (ej: ≤ -2.0)
///
/// # Referencia:
/// WMO Manual on Codes, Code Table 0266 (CAR - Characteristic of pressure tendency)
fn calc_car(pres_est: &str, p3: &str) -> String {
    if let (Ok(pe), Ok(p)) = (pres_est.parse::<f64>(), p3.parse::<f64>()) {
        let dif = pe - p; // NOTA: no usar abs(), necesitamos el signo
        let abs_dif = dif.abs();

        if dif == 0.0 {
            return "4".to_string();
        }

        if dif > 0.0 {
            // Presión aumentó
            if abs_dif >= 0.1 && abs_dif <= 0.5 {
                return "0".to_string();
            }
            if abs_dif >= 0.6 && abs_dif <= 1.4 {
                return "1".to_string();
            }
            if abs_dif >= 1.5 && abs_dif <= 1.9 {
                return "2".to_string();
            }
            if abs_dif >= 2.0 {
                return "3".to_string();
            }
        } else {
            // Presión disminuyó
            if abs_dif >= 0.1 && abs_dif <= 0.5 {
                return "5".to_string();
            }
            if abs_dif >= 0.6 && abs_dif <= 1.4 {
                return "6".to_string();
            }
            if abs_dif >= 1.5 && abs_dif <= 1.9 {
                return "7".to_string();
            }
            if abs_dif >= 2.0 {
                return "8".to_string();
            }
        }
    }
    String::new()
}

/// Calcular tiempo presente (campo ww del grupo 7wwW1W2)
///
/// # Lógica:
/// 1. Si el grupo 7wwW1W2 tiene valor válido (mínimo 3 caracteres, sin '/' en ww):
///    - Extraer caracteres 2 y 3 (índices 1 y 2) → ese es el código ww
/// 2. Si no tiene valor, calcular por comparación de nubosidad (N de Nddff):
///    - N actual > N anterior → "01" (aumentó)
///    - N actual = N anterior → "02" (sin cambio)
///    - N actual < N anterior → "03" (decreció)
fn calc_tiempo_presente(seven_ww: &str, nddff_current: &str, nddff_prev: &str) -> String {
    // Caso 1: Extraer desde grupo 7wwW1W2
    // El formato es "7wwW1W2" donde ww son los caracteres 2 y 3 (índices 1 y 2)
    if seven_ww.len() >= 3 {
        let ww_chars = &seven_ww[1..3];
        // Verificar que no tenga '/' (carácter de dato faltante)
        if !ww_chars.contains('/') {
            return ww_chars.to_string();
        }
    }

    // Caso 2: Calcular por comparación de nubosidad (N de Nddff)
    // N es el primer carácter del grupo Nddff
    if !nddff_current.is_empty() && !nddff_prev.is_empty() {
        let curr = nddff_current.chars().next().unwrap_or('0');
        let prev = nddff_prev.chars().next().unwrap_or('0');

        // Ignorar si N es '/' (dato faltante)
        if curr != '/' && prev != '/' {
            return if curr > prev {
                "01".to_string() // N aumentó
            } else if curr == prev {
                "02".to_string() // N sin cambio
            } else {
                "03".to_string() // N decreció
            };
        }
    }

    // Sin datos suficientes
    String::new()
}

/// Obtener la hora sinóptica anterior (3 horas antes)
///
/// # Mapeo de horas sinópticas:
/// - Las observaciones sinópticas se hacen cada 3 horas UTC
/// - 06Z → 03Z, 09Z → 06Z, etc.
///
/// # Uso:
/// Necesario para comparar datos de la hora actual con la anterior
/// (ej: comparar Nddff actual vs anterior para calcular tiempo presente)
fn get_prev_hour(hora: &str) -> &'static str {
    match hora {
        "09Z" => "06Z",
        "12Z" => "09Z",
        "15Z" => "12Z",
        "18Z" => "15Z",
        "21Z" => "18Z",
        "00Z" => "21Z",
        "03Z" => "00Z",
        "06Z" => "03Z",
        _ => "",
    }
}

#[tauri::command]
pub fn save_observation_json(
    app_handle: AppHandle,
    station_code: String,
    fecha: String,
    observations: Value,
    observer_name: Option<String>,
) -> Result<HashMap<String, String>, String> {
    let (year, month) = parse_date_parts(&fecha);

    // Nueva ruta: Documents/ARCA/synoptic/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "synoptic");
    let dir_path = ensure_arca_dirs(&base_dir, &year, &month)?;

    let fecha_formatted = format_date_for_filename(&fecha);
    let filename = format!("{}{}.json", station_code, fecha_formatted);
    let filepath = dir_path.join(&filename);

    let backup_path = create_backup(&filepath, &station_code, &app_handle).unwrap_or_default();

    // Transformar a nueva estructura
    let mut new_structure = serde_json::Map::new();

    // --- META ---
    let mut meta = serde_json::Map::new();
    meta.insert("estacion".to_string(), Value::String(station_code.clone()));
    meta.insert("fecha".to_string(), Value::String(fecha_formatted.clone()));
    if let Some(name) = observer_name {
        meta.insert("observador".to_string(), Value::String(name));
    }
    meta.insert(
        "ultima_actualizacion".to_string(),
        Value::String(chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()),
    );
    new_structure.insert("meta".to_string(), Value::Object(meta));

    // --- HORAS ---
    let mut horas_map = serde_json::Map::new();

    if let Some(horas_obj) = observations.as_object() {
        for (hora_key, hora_data) in horas_obj {
            if let Some(hora_data_obj) = hora_data.as_object() {
                let mut hora_structure = serde_json::Map::new();

                // - DATOS: campos que el usuario digita
                let mut datos = serde_json::Map::new();
                // ts, th
                if let Some(v) = hora_data_obj.get("ts") {
                    datos.insert("ts".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("th") {
                    datos.insert("th".to_string(), v.clone());
                }
                // pres_est, p3, p24
                if let Some(v) = hora_data_obj.get("pres_est") {
                    datos.insert("pres_est".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("p3") {
                    datos.insert("p3".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("p24") {
                    datos.insert("p24".to_string(), v.clone());
                }
                // viento
                if let Some(v) = hora_data_obj.get("viento_dir") {
                    datos.insert("viento_dir".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("viento_vel") {
                    datos.insert("viento_vel".to_string(), v.clone());
                }
                // visibilidad
                if let Some(v) = hora_data_obj.get("visibilidad") {
                    datos.insert("visibilidad".to_string(), v.clone());
                }
                // Tmax, Tmin, LL
                if let Some(v) = hora_data_obj.get("t_max") {
                    datos.insert("Tmax".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("t_min") {
                    datos.insert("Tmin".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("ll") {
                    datos.insert("LL".to_string(), v.clone());
                }
                // Tmax_24h, Tmin_24h, LL_24h
                if let Some(v) = hora_data_obj.get("t_max_24h") {
                    datos.insert("Tmax_24h".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("t_min_24h") {
                    datos.insert("Tmin_24h".to_string(), v.clone());
                }
                if let Some(v) = hora_data_obj.get("ll_24h") {
                    datos.insert("LL_24h".to_string(), v.clone());
                }
                // campos SYNOP - convertir nombres frontend a nombres SYNOP OMM
                let mut synop = serde_json::Map::new();
                for (key, value) in hora_data_obj.iter() {
                    if key.starts_with("meteo_") || key.starts_with("extra_") {
                        let synop_name = to_synop_name(key);
                        synop.insert(synop_name, value.clone());
                    }
                }
                if !synop.is_empty() {
                    hora_structure.insert("synop".to_string(), Value::Object(synop));
                }
                if !datos.is_empty() {
                    hora_structure.insert("datos".to_string(), Value::Object(datos));
                }

                // - CALCULADO: campos calculados automaticamente
                let mut calculado = serde_json::Map::new();
                if let Some(v) = hora_data_obj.get("pres_nmm") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("pres_nmm".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("punto_rocio") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("pr".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("tension_vapor") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("tv".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("humedad_relativa") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("hr".to_string(), v.clone());
                    }
                }
                if let Some(v) = hora_data_obj.get("diferencia") {
                    if !v.is_null() && !v.as_str().unwrap_or("").is_empty() {
                        calculado.insert("dif".to_string(), v.clone());
                    }
                }
                if !calculado.is_empty() {
                    hora_structure.insert("calculado".to_string(), Value::Object(calculado));
                }

                horas_map.insert(hora_key.clone(), Value::Object(hora_structure));
            }
        }
    }

    new_structure.insert("horas".to_string(), Value::Object(horas_map));

    let data_str = serde_json::to_string_pretty(&new_structure).map_err(|e| e.to_string())?;
    fs::write(&filepath, data_str).map_err(|e| e.to_string())?;

    let mut res = HashMap::new();
    res.insert("success".to_string(), "true".to_string());
    res.insert(
        "filepath".to_string(),
        filepath.to_string_lossy().to_string(),
    );
    res.insert("filename".to_string(), filename);
    res.insert("backup_path".to_string(), backup_path);

    Ok(res)
}

#[tauri::command]
pub fn get_observations_list(
    app_handle: AppHandle,
    station_code: Option<String>,
) -> Result<HashMap<String, Value>, String> {
    // Nueva ruta: Documents/ARCA/synoptic/
    let base_dir = get_arca_base_dir(&app_handle, "synoptic");

    let mut files = Vec::new();

    let target_dir = if let Some(ref st) = station_code {
        base_dir.join(st)
    } else {
        base_dir.clone()
    };

    if target_dir.exists() {
        let walker = walkdir::WalkDir::new(&target_dir);
        for entry in walker.into_iter().filter_map(|e| e.ok()) {
            if entry.path().is_file() {
                if let Some(ext) = entry.path().extension() {
                    if ext == "json" {
                        if let Ok(rel) = entry.path().strip_prefix(&base_dir) {
                            files.push(Value::String(rel.to_string_lossy().to_string()));
                        }
                    }
                }
            }
        }
    }

    files.sort_by(|a, b| {
        let s1 = a.as_str().unwrap_or("");
        let s2 = b.as_str().unwrap_or("");
        s1.cmp(s2)
    });

    let count = files.len() as i64;
    let mut res = HashMap::new();
    res.insert("files".to_string(), Value::Array(files));
    res.insert(
        "count".to_string(),
        Value::Number(serde_json::Number::from(count)),
    );

    Ok(res)
}

#[tauri::command]
pub fn get_observation(
    app_handle: AppHandle,
    station_code: String,
    fecha: String,
) -> Result<Value, String> {
    let (year, month) = parse_date_parts(&fecha);
    let fecha_formatted = format_date_for_filename(&fecha);
    let filename = format!("{}{}.json", station_code, fecha_formatted);

    // Nueva ruta: Documents/ARCA/synoptic/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "synoptic");
    let mut filepath = base_dir.clone();
    filepath.push(&year);
    filepath.push(&month);
    filepath.push(&filename);

    if filepath.exists() {
        let data = fs::read_to_string(&filepath).map_err(|e| e.to_string())?;
        let json: Value = serde_json::from_str(&data).map_err(|e| e.to_string())?;

        // Transformar nueva estructura al formato del frontend (flattened)
        // Se OMITEN los campos en "calculado" - se recalculan automaticamente
        let mut result = serde_json::Map::new();

        if let Some(json_obj) = json.as_object() {
            // Incluir meta
            if let Some(meta) = json_obj.get("meta") {
                if let Some(meta_obj) = meta.as_object() {
                    if let Some(v) = meta_obj.get("estacion") {
                        result.insert("station_id".to_string(), v.clone());
                    }
                    if let Some(fecha_val) = meta_obj.get("fecha") {
                        // Convertir DDMMAA a YYYY-MM-DD
                        let f = fecha_val.as_str().unwrap_or("");
                        if f.len() == 6 {
                            let dd = &f[0..2];
                            let mm = &f[2..4];
                            let aa = &f[4..6];
                            let yyyy = format!("20{}", aa);
                            result.insert(
                                "fecha".to_string(),
                                Value::String(format!("{}-{}-{}", yyyy, mm, dd)),
                            );
                        }
                    }
                    if let Some(v) = meta_obj.get("observador") {
                        result.insert("observador".to_string(), v.clone());
                    }
                }
            }

            // Procesar horas
            if let Some(horas) = json_obj.get("horas") {
                if let Some(horas_obj) = horas.as_object() {
                    for (hora_key, hora_data) in horas_obj.iter() {
                        if let Some(hora_obj) = hora_data.as_object() {
                            let mut flat_hora = serde_json::Map::new();

                            // Extraer datos y synop para cálculos
                            let datos = hora_obj.get("datos").and_then(|d| d.as_object());
                            let synop = hora_obj.get("synop").and_then(|s| s.as_object());

                            // DATOS → misma estrutura flattened
                            if let Some(datos_obj) = datos {
                                for (key, value) in datos_obj.iter() {
                                    flat_hora.insert(key.clone(), value.clone());
                                }
                            }

                            // SYNOP → convertir nombres SYNOP a nombres frontend
                            if let Some(synop_obj) = synop {
                                for (key, value) in synop_obj.iter() {
                                    let frontend_name = to_frontend_name(key);
                                    flat_hora.insert(frontend_name, value.clone());
                                }
                            }

                            // ========== CALCULAR CAMPOS AUTOMÁTICOS ==========
                            // Obtener valores necesarios
                            let pres_est = datos
                                .and_then(|d| d.get("pres_est"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");
                            let p3 = datos
                                .and_then(|d| d.get("p3"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");
                            let irixhv = synop
                                .and_then(|s| s.get("IrIXHVV"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");
                            let seven_ww = synop
                                .and_then(|s| s.get("7wwW1W2"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");
                            let nddff_actual = synop
                                .and_then(|s| s.get("Nddff"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");

                            // Obtener hora anterior y sus datos
                            let prev_hora_key = get_prev_hour(hora_key);
                            let nddff_anterior = horas_obj
                                .get(prev_hora_key)
                                .and_then(|h| h.as_object())
                                .and_then(|h| h.get("synop"))
                                .and_then(|s| s.as_object())
                                .and_then(|s| s.get("Nddff"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("");

                            // Calcular y agregar campos automáticos
                            let dif = calc_dif(pres_est, p3);
                            let car = calc_car(pres_est, p3);
                            let visibilidad = get_visibilidad_from_irixhv(irixhv);
                            let tiempo_presente =
                                calc_tiempo_presente(seven_ww, nddff_actual, nddff_anterior);

                            if !dif.is_empty() {
                                flat_hora.insert("tend_dif".to_string(), Value::String(dif));
                            }
                            if !car.is_empty() {
                                flat_hora.insert("tend_car".to_string(), Value::String(car));
                            }
                            if !visibilidad.is_empty() {
                                flat_hora
                                    .insert("visibilidad".to_string(), Value::String(visibilidad));
                            }
                            if !tiempo_presente.is_empty() {
                                flat_hora.insert(
                                    "tiempo_presente".to_string(),
                                    Value::String(tiempo_presente),
                                );
                            }

                            // Preservar estacion y correc_alt
                            if let Some(st_id) = result.get("station_id") {
                                flat_hora.insert("station_id".to_string(), st_id.clone());
                            }
                            if let Some(correc) = result.get("correc_alt") {
                                flat_hora.insert("correc_alt".to_string(), correc.clone());
                            }

                            result.insert(hora_key.clone(), Value::Object(flat_hora));
                        }
                    }
                }
            }
        }

        Ok(Value::Object(result))
    } else {
        Err("Observacion no encontrada".to_string())
    }
}

#[tauri::command]
pub fn get_station_date_range(
    app_handle: AppHandle,
    station_code: String,
) -> Result<HashMap<String, Value>, String> {
    let station_dir = get_base_data_dir(&app_handle).join(&station_code);

    let mut dates = Vec::new();
    if station_dir.exists() {
        let walker = walkdir::WalkDir::new(&station_dir);
        for entry in walker.into_iter().filter_map(|e| e.ok()) {
            if entry.file_type().is_file()
                && entry.path().extension().map_or(false, |ext| ext == "json")
            {
                let fname = entry
                    .path()
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy();
                if fname.len() >= 8 {
                    let date_str = &fname[fname.len() - 8..];
                    let dd = &date_str[0..2];
                    let mm = &date_str[2..4];
                    let yyyy = &date_str[4..8];
                    dates.push(format!("{}-{}-{}", yyyy, mm, dd));
                }
            }
        }
    }

    dates.sort();

    let oldest = dates
        .first()
        .map(|s| Value::String(s.clone()))
        .unwrap_or(Value::Null);
    let newest = dates
        .last()
        .map(|s| Value::String(s.clone()))
        .unwrap_or(Value::Null);
    let has_data = !dates.is_empty();

    let mut res = HashMap::new();
    res.insert("station_code".to_string(), Value::String(station_code));
    res.insert("oldest_date".to_string(), oldest);
    res.insert("newest_date".to_string(), newest);
    Ok(res)
}

#[tauri::command]
pub fn save_cli3074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
    data: Value,
) -> Result<String, String> {
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("La fecha debe tener formato YYYY-MM-DD".to_string());
    }

    let year = parts[0];
    let month = parts[1];

    // Nueva ruta: Documents/ARCA/cli3074/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "cli3074");
    let target_dir = ensure_arca_dirs(&base_dir, year, month)?;

    let file_name = format!("{}_{}_{}.json", station_id, date, "cli3074");
    let mut file_path = target_dir;
    file_path.push(file_name);

    let json_string = serde_json::to_string_pretty(&data).map_err(|e| e.to_string())?;

    fs::write(&file_path, json_string).map_err(|e| format!("Error escribiendo archivo: {}", e))?;

    Ok(format!("Guardado en: {}", file_path.display()))
}

#[tauri::command]
pub fn load_cli3074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
) -> Result<Value, String> {
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha inválido".to_string());
    }
    let year = parts[0];
    let month = parts[1];

    // Nueva ruta: Documents/ARCA/cli3074/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "cli3074");
    let mut file_path = base_dir.clone();
    file_path.push(year);
    file_path.push(month);

    let file_name = format!("{}_{}_{}.json", station_id, date, "cli3074");
    file_path.push(file_name);

    if !file_path.exists() {
        return Ok(Value::Null);
    }

    let contents = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
    let json_val: Value = serde_json::from_str(&contents).map_err(|e| e.to_string())?;

    // ========== CALCULAR CAMPOS AUTOMÁTICOS ==========
    // El JSON tiene { "horas": { "1": {...}, "2": {...}, ... } }
    // Necesitamos calcular para cada hora
    if let Some(json_obj) = json_val.as_object() {
        if let Some(horas) = json_obj.get("horas") {
            if let Some(horas_obj) = horas.as_object() {
                let mut new_horas = serde_json::Map::new();

                for (hora_key, hora_data) in horas_obj.iter() {
                    if let Some(hora_obj) = hora_data.as_object() {
                        let mut new_hora = hora_obj.clone();

                        // Extraer datos para cálculos
                        let pres_est = hora_obj
                            .get("pres_est")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        let p3 = hora_obj.get("p3").and_then(|v| v.as_str()).unwrap_or("");

                        // Calcular tend_dif (DIF) en formato 00.0
                        // Primero: si ya existe tend_dif en formato "000", convertir a "00.0"
                        let existing_dif = hora_obj
                            .get("tend_dif")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        let dif = if !existing_dif.is_empty() {
                            format_dif(existing_dif)
                        } else {
                            calc_dif(pres_est, p3)
                        };
                        if !dif.is_empty() {
                            new_hora.insert("tend_dif".to_string(), Value::String(dif));
                        }

                        // Calcular CAR (característica de tendencia)
                        let existing_car = hora_obj
                            .get("tend_car")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        let car = if existing_car.is_empty() {
                            calc_car(pres_est, p3)
                        } else {
                            existing_car.to_string()
                        };
                        if !car.is_empty() {
                            new_hora.insert("tend_car".to_string(), Value::String(car));
                        }

                        // Calcular visibilidad desde IrIxHVV (si existe)
                        let irixhv = hora_obj
                            .get("meteo_4_irixhvv")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        let visibilidad = get_visibilidad_from_irixhv(irixhv);
                        if !visibilidad.is_empty() {
                            new_hora.insert("visibilidad".to_string(), Value::String(visibilidad));
                        }

                        // Calcular tiempo presente
                        let seven_ww = hora_obj
                            .get("meteo_4_6")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        let nddff = hora_obj
                            .get("meteo_4_1")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");

                        // Buscar hora anterior
                        let prev_hour = match hora_key.as_str() {
                            "1" => None,
                            "2" => Some("1"),
                            "3" => Some("2"),
                            "4" => Some("3"),
                            "5" => Some("4"),
                            "6" => Some("5"),
                            "7" => Some("6"),
                            "8" => Some("7"),
                            "9" => Some("8"),
                            "10" => Some("9"),
                            "11" => Some("10"),
                            "12" => Some("11"),
                            "13" => Some("12"),
                            "14" => Some("13"),
                            "15" => Some("14"),
                            "16" => Some("15"),
                            "17" => Some("16"),
                            "18" => Some("17"),
                            "19" => Some("18"),
                            "20" => Some("19"),
                            "21" => Some("20"),
                            "22" => Some("21"),
                            "23" => Some("22"),
                            "24" => Some("23"),
                            _ => None,
                        };

                        let nddff_prev = if let Some(ph) = prev_hour {
                            horas_obj
                                .get(ph)
                                .and_then(|h| h.as_object())
                                .and_then(|h| h.get("meteo_4_1"))
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                        } else {
                            ""
                        };

                        let tiempo_presente = calc_tiempo_presente(seven_ww, nddff, nddff_prev);
                        if !tiempo_presente.is_empty() {
                            new_hora.insert(
                                "tiempo_presente".to_string(),
                                Value::String(tiempo_presente),
                            );
                        }

                        new_horas.insert(hora_key.clone(), Value::Object(new_hora));
                    } else {
                        new_horas.insert(hora_key.clone(), hora_data.clone());
                    }
                }

                // Reconstruir el JSON con los cálculos
                let mut result = json_obj.clone();
                result.insert("horas".to_string(), Value::Object(new_horas));
                return Ok(Value::Object(result));
            }
        }
    }

    Ok(json_val)
}

// =============================================================================
// CLI 4074 - Nubosidad y Temperatura
// =============================================================================

/// Guardar formulario CLI 4074 (Nubosidad y Temperatura)
///
/// # Estructura del JSON:
/// Documents/ARCA/cli4074/{year}/{month}/{station}_{date}_cli4074.json
#[tauri::command]
pub fn save_cli4074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
    data: Value,
) -> Result<HashMap<String, String>, String> {
    let (year, month) = parse_date_parts(&date);

    // Ruta: Documents/ARCA/cli4074/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "cli4074");
    let mut file_path = base_dir.clone();
    file_path.push(&year);
    file_path.push(&month);

    // Crear directorios si no existen
    fs::create_dir_all(&file_path).map_err(|e| e.to_string())?;

    let file_name = format!("{}_{}_{}.json", station_id, date, "cli4074");
    file_path.push(file_name);

    let json_string = serde_json::to_string_pretty(&data).map_err(|e| e.to_string())?;
    fs::write(&file_path, json_string).map_err(|e| e.to_string())?;

    let mut result = HashMap::new();
    result.insert("status".to_string(), "saved".to_string());
    result.insert("path".to_string(), file_path.to_string_lossy().to_string());
    Ok(result)
}

/// Cargar formulario CLI 4074 (Nubosidad y Temperatura)
///
/// # Estructura del JSON:
/// Documents/ARCA/cli4074/{year}/{month}/{station}_{date}_cli4074.json
#[tauri::command]
pub fn load_cli4074_json(
    app_handle: AppHandle,
    station_id: String,
    date: String,
) -> Result<Value, String> {
    let parts: Vec<&str> = date.split('-').collect();
    if parts.len() != 3 {
        return Err("Formato de fecha inválido".to_string());
    }
    let year = parts[0];
    let month = parts[1];

    // Ruta: Documents/ARCA/cli4074/{year}/{month}/
    let base_dir = get_arca_base_dir(&app_handle, "cli4074");
    let mut file_path = base_dir.clone();
    file_path.push(year);
    file_path.push(month);

    let file_name = format!("{}_{}_{}.json", station_id, date, "cli4074");
    file_path.push(file_name);

    if !file_path.exists() {
        return Ok(Value::Null);
    }

    let contents = fs::read_to_string(&file_path).map_err(|e| e.to_string())?;
    let json_val: Value = serde_json::from_str(&contents).map_err(|e| e.to_string())?;

    Ok(json_val)
}
