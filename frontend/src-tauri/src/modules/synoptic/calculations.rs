use crate::db::DbPool;
use crate::repositories::stations_repo::{self, StationInfo};
use serde::{Deserialize, Serialize};

pub fn get_station_info(pool: &DbPool, station_id: &str) -> Option<StationInfo> {
    stations_repo::get_station_by_id(pool, station_id).unwrap_or(None)
}

// =============================================================================
// CÁLCULOS METEOROLÓGICOS (psicrométricos)
// =============================================================================

fn calcular_h26(temp_humedo: f64) -> Option<f64> {
    if (temp_humedo + 243.5).abs() < f64::EPSILON {
        return None;
    }
    Some(6.112 * ((17.67 * temp_humedo) / (temp_humedo + 243.5)).exp())
}

fn calcular_h27(temp_humedo: f64) -> f64 {
    0.00066 * 1000.0 * (1.0 + 0.00115 * temp_humedo)
}

fn calcular_h28_asumido(temp_seco: f64) -> Option<f64> {
    if (temp_seco + 243.5).abs() < f64::EPSILON {
        return None;
    }
    Some(6.112 * ((17.67 * temp_seco) / (temp_seco + 243.5)).exp())
}

fn calcular_tension_vapor(temp_seco: f64, temp_humedo: f64) -> Option<f64> {
    let h26 = calcular_h26(temp_humedo)?;
    let h27 = calcular_h27(temp_humedo);
    Some(h26 - h27 * (temp_seco - temp_humedo))
}

fn calcular_humedad_relativa(tension_vapor: f64, temp_seco: f64) -> Option<f64> {
    let h28_asumido = calcular_h28_asumido(temp_seco)?;
    if h28_asumido == 0.0 {
        return None;
    }
    Some((tension_vapor / h28_asumido) * 100.0)
}

fn calcular_punto_rocio(temp_seco: f64, humedad_relativa_porc: f64) -> Option<f64> {
    let factor_humedad = 1.0 - (0.01 * humedad_relativa_porc);
    let termino1 = (14.55 + 0.114 * temp_seco) * factor_humedad;
    let termino2 = ((2.5 + 0.007 * temp_seco) * factor_humedad).powf(3.0);
    let termino3 = (15.9 + 0.117 * temp_seco) * factor_humedad.powf(14.0);
    let result = temp_seco - termino1 - termino2 - termino3;
    if result.is_nan() || result.is_infinite() {
        None
    } else {
        Some(result)
    }
}

// =============================================================================
// CODIFICACIÓN SYNOP (WMO FM-12)
// =============================================================================

fn format_temperature_group(temp: Option<f64>) -> String {
    if let Some(t) = temp {
        let sign = if t >= 0.0 { "0" } else { "1" };
        let ttt = format!("{:03}", (t.abs() * 10.0).round() as i32);
        format!("1{}{}", sign, ttt)
    } else {
        "".to_string()
    }
}

fn format_dew_point_group(dew_point: Option<f64>) -> String {
    if let Some(dp) = dew_point {
        let sign = if dp >= 0.0 { "0" } else { "1" };
        let ttt = format!("{:03}", (dp.abs() * 10.0).round() as i32);
        format!("2{}{}", sign, ttt)
    } else {
        "".to_string()
    }
}

fn format_pressure_group(pressure: Option<f64>) -> String {
    if let Some(p) = pressure {
        let pppp = format!("{:04}", ((p * 10.0).round() as i32) % 10000);
        format!("4{}", pppp)
    } else {
        "".to_string()
    }
}

fn calcular_tendencia_a(dif: f64) -> String {
    let abs_dif = dif.abs();
    if dif == 0.0 {
        return "4".to_string();
    }
    if dif > 0.0 {
        if (0.1..=0.5).contains(&abs_dif) {
            return "0".to_string();
        }
        if (0.6..=1.4).contains(&abs_dif) {
            return "1".to_string();
        }
        if (1.5..=1.9).contains(&abs_dif) {
            return "2".to_string();
        }
        if abs_dif >= 2.0 {
            return "3".to_string();
        }
    }
    if dif < 0.0 {
        if (0.1..=0.5).contains(&abs_dif) {
            return "5".to_string();
        }
        if (0.6..=1.4).contains(&abs_dif) {
            return "6".to_string();
        }
        if (1.5..=1.9).contains(&abs_dif) {
            return "7".to_string();
        }
        if abs_dif >= 2.0 {
            return "8".to_string();
        }
    }
    "4".to_string()
}

fn format_pressure_tendency_group(diferencia_p3: Option<f64>) -> String {
    if let Some(dif) = diferencia_p3 {
        let dif_rounded = (dif * 10.0).round() / 10.0;
        let a = calcular_tendencia_a(dif_rounded);
        let ppp = format!("{:03}", (dif_rounded.abs() * 10.0).round() as i32);
        format!("5{}{}", a, ppp)
    } else {
        "".to_string()
    }
}

fn format_pressure_24h_group(diferencia_p24: Option<f64>) -> String {
    if let Some(dif) = diferencia_p24 {
        let dif_rounded = (dif * 10.0).round() / 10.0;
        let prefix = if dif_rounded >= 0.0 { "58" } else { "59" };
        let ppp = format!("{:03}", (dif_rounded.abs() * 10.0).round() as i32);
        format!("{}{}", prefix, ppp)
    } else {
        "".to_string()
    }
}

fn format_humidity_group(humedad_relativa: Option<f64>) -> String {
    if let Some(hr) = humedad_relativa {
        let val = hr.clamp(0.0, 100.0).round() as i32;
        format!("29{:03}", val)
    } else {
        "".to_string()
    }
}

fn should_include_precipitation(ir: &str) -> bool {
    matches!(ir, "0" | "1" | "2")
}

fn should_include_weather(ix: &str) -> bool {
    matches!(ix, "1" | "4")
}

// =============================================================================
// WMO — tablas y mapeos SYNOP (fuente única, ponytail: antes duplicado ×3)
// =============================================================================

const FRONTEND_TO_SYNOP: &[(&str, &str)] = &[
    ("meteo_2_1", "YYGGiw"),
    ("meteo_4_irixhvv", "IrIXHVV"),
    ("meteo_4_1", "Nddff"),
    ("meteo_4_6", "7wwW1W2"),
    ("meteo_6_0", "8NhCLCMCH"),
    ("meteo_6_2", "0CSDL DM DH"),
    ("meteo_6_3", "1snTxTxTx"),
    ("meteo_6_4", "2snTnTnTn"),
    ("meteo_6_5", "3Ejjj"),
    ("meteo_6_6", "5EEEjE"),
    ("meteo_8_0", "5nFnFnFn"),
    ("meteo_8_1", "56DLDMDH"),
    ("meteo_8_3", "6RRRtr"),
    ("meteo_8_4", "7R24R24R24R24"),
    ("meteo_8_5", "8NsChshs_1"),
    ("meteo_8_6", "8NsChshs_2"),
    ("extra_8ns_1", "8NsChshs_3"),
    ("extra_8ns_2", "8NsChshs_4"),
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

pub fn to_synop_name(frontend_name: &str) -> String {
    for (from, to) in FRONTEND_TO_SYNOP.iter() {
        if *from == frontend_name {
            return to.to_string();
        }
    }
    frontend_name.to_string()
}

pub fn to_frontend_name(synop_name: &str) -> String {
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

pub fn get_visibilidad_from_irixhv(irixhv: &str) -> String {
    let table: [(&str, &str); 75] = [
        ("00", "000"), ("01", "001"), ("02", "002"), ("03", "003"), ("04", "004"),
        ("05", "005"), ("06", "006"), ("07", "007"), ("08", "008"), ("09", "009"),
        ("10", "010"), ("11", "011"), ("12", "012"), ("13", "013"), ("14", "014"),
        ("15", "015"), ("16", "016"), ("17", "017"), ("18", "018"), ("19", "019"),
        ("20", "020"), ("21", "021"), ("22", "022"), ("23", "023"), ("24", "024"),
        ("25", "025"), ("26", "026"), ("27", "027"), ("28", "028"), ("29", "029"),
        ("30", "030"), ("31", "031"), ("32", "032"), ("33", "033"), ("34", "034"),
        ("35", "035"), ("36", "036"), ("37", "037"), ("38", "038"), ("39", "039"),
        ("40", "040"), ("41", "041"), ("42", "042"), ("43", "043"), ("44", "044"),
        ("45", "045"), ("46", "046"), ("47", "047"), ("48", "048"), ("49", "049"),
        ("56", "060"), ("57", "070"), ("58", "080"), ("59", "090"), ("60", "100"),
        ("61", "110"), ("62", "120"), ("63", "130"), ("64", "140"), ("65", "150"),
        ("66", "160"), ("67", "170"), ("68", "180"), ("69", "190"), ("70", "200"),
        ("71", "210"), ("72", "220"), ("73", "230"), ("74", "240"), ("75", "250"),
        ("76", "260"), ("77", "270"), ("78", "280"), ("79", "290"), ("80", "300"),
    ];
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

pub fn format_dif(dif_value: &str) -> String {
    if dif_value.is_empty() {
        return String::new();
    }
    if dif_value.len() == 4 && dif_value.contains('.') {
        return dif_value.to_string();
    }
    if dif_value.len() == 3 {
        let chars: Vec<char> = dif_value.chars().collect();
        return format!("{}{}.{}", chars[0], chars[1], chars[2]);
    }
    if dif_value.len() == 4 {
        let chars: Vec<char> = dif_value.chars().collect();
        return format!("{}{}.{}{}", chars[0], chars[1], chars[2], chars[3]);
    }
    dif_value.to_string()
}

pub fn calc_dif(pres_est: &str, p3: &str) -> String {
    if let (Ok(pe), Ok(p)) = (pres_est.parse::<f64>(), p3.parse::<f64>()) {
        let dif = (pe - p).abs();
        return format!("{:04.1}", dif);
    }
    String::new()
}

pub fn calc_car(pres_est: &str, p3: &str) -> String {
    if let (Ok(pe), Ok(p)) = (pres_est.parse::<f64>(), p3.parse::<f64>()) {
        let dif = pe - p;
        return calcular_tendencia_a(dif);
    }
    String::new()
}

pub fn calc_tiempo_presente(seven_ww: &str, nddff_current: &str, nddff_prev: &str) -> String {
    if seven_ww.len() >= 3 {
        let ww_chars = &seven_ww[1..3];
        if !ww_chars.contains('/') {
            return ww_chars.to_string();
        }
    }
    if !nddff_current.is_empty() && !nddff_prev.is_empty() {
        let curr = nddff_current.chars().next().unwrap_or('0');
        let prev = nddff_prev.chars().next().unwrap_or('0');
        if curr != '/' && prev != '/' {
            return if curr > prev {
                "01".to_string()
            } else if curr == prev {
                "02".to_string()
            } else {
                "03".to_string()
            };
        }
    }
    String::new()
}

pub fn get_prev_hour(hora: &str) -> &'static str {
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

// =============================================================================
// I/O STRUCTURES
// =============================================================================

#[derive(Deserialize, Debug)]
pub struct CalculationRequest {
    pub station_id: Option<String>,
    pub correc_alt: Option<String>,
    pub ts: Option<String>,
    pub th: Option<String>,
    pub pres_est: Option<String>,
    pub p3: Option<String>,
    pub p24: Option<String>,
    pub ir: Option<String>,
    pub ix: Option<String>,
}

#[derive(Serialize)]
pub struct CalculationResponse {
    pub tension_vapor: String,
    pub humedad_relativa: String,
    pub punto_rocio: String,
    pub diferencia: String,

    pub grupo_1sn_ttt: String,
    pub grupo_2sn_td: String,
    pub grupo_4pppp: String,
    pub grupo_5appp: String,
    pub grupo_58_59_p24: String,
    pub grupo_29uuu: String,

    pub p3_let: String,
    pub p24_let: String,
    pub p3_dif: String,
    pub p24_dif: String,
    pub pres_nmm: String,
    pub correc_alt: String,

    pub include_precipitation: bool,
    pub include_weather: bool,

    pub station_info: Option<StationInfo>,
    pub error_message: String,
}

// =============================================================================
// ALGORITMO PRINCIPAL
// =============================================================================

pub fn realizar_calculos(pool: &DbPool, data: CalculationRequest) -> CalculationResponse {
    let mut res = CalculationResponse {
        tension_vapor: "".to_string(),
        humedad_relativa: "".to_string(),
        punto_rocio: "".to_string(),
        diferencia: "".to_string(),
        grupo_1sn_ttt: "".to_string(),
        grupo_2sn_td: "".to_string(),
        grupo_4pppp: "".to_string(),
        grupo_5appp: "".to_string(),
        grupo_58_59_p24: "".to_string(),
        grupo_29uuu: "".to_string(),
        p3_let: "".to_string(),
        p24_let: "".to_string(),
        p3_dif: "".to_string(),
        p24_dif: "".to_string(),
        pres_nmm: "".to_string(),
        correc_alt: "".to_string(),
        include_precipitation: true,
        include_weather: true,
        station_info: None,
        error_message: "".to_string(),
    };

    if let Some(st_id) = &data.station_id {
        if let Some(info) = get_station_info(pool, st_id) {
            res.correc_alt = info.ch.to_string();
            res.station_info = Some(info);
        }
    }
    if res.correc_alt.is_empty() {
        if let Some(ca) = &data.correc_alt {
            res.correc_alt = ca.clone();
        }
    }

    let ts_val = data.ts.as_ref().and_then(|s| s.parse::<f64>().ok());
    let th_val = data.th.as_ref().and_then(|s| s.parse::<f64>().ok());

    if let Some(ts) = ts_val {
        res.grupo_1sn_ttt = format_temperature_group(Some(ts));
    }

    if let (Some(ts), Some(th)) = (ts_val, th_val) {
        if th > ts {
            res.error_message = "Error: Th no puede ser mayor que Ts.".to_string();
        } else {
            if let Some(tv) = calcular_tension_vapor(ts, th) {
                res.tension_vapor = format!("{:.1}", tv);
                if let Some(hr) = calcular_humedad_relativa(tv, ts) {
                    res.humedad_relativa = format!("{:.0}", hr.clamp(0.0, 100.0));
                    if let Some(pr) = calcular_punto_rocio(ts, hr) {
                        res.punto_rocio = format!("{:.1}", pr);
                        res.grupo_2sn_td = format_dew_point_group(Some(pr));
                    }
                    res.grupo_29uuu = format_humidity_group(Some(hr));
                }
            }
            res.diferencia = format!("{:.1}", ts - th);
            res.grupo_1sn_ttt = format_temperature_group(Some(ts));
        }
    }

    let pres_est_val = data.pres_est.as_ref().and_then(|s| s.parse::<f64>().ok());
    let p3_val = data.p3.as_ref().and_then(|s| s.parse::<f64>().ok());
    let p24_val = data.p24.as_ref().and_then(|s| s.parse::<f64>().ok());
    let correc_alt_val = res.correc_alt.parse::<f64>().ok();

    if let Some(pe) = pres_est_val {
        res.p3_let = format!("{:.1}", pe);
        res.p24_let = format!("{:.1}", pe);

        if let Some(p3) = p3_val {
            let dif = pe - p3;
            res.p3_dif = format!("{:.1}", dif);
            res.grupo_5appp = format_pressure_tendency_group(Some(dif));
        }

        if let Some(p24) = p24_val {
            let dif = pe - p24;
            res.p24_dif = format!("{:.1}", dif);
            res.grupo_58_59_p24 = format_pressure_24h_group(Some(dif));
        }

        if let Some(ca) = correc_alt_val {
            let p_nmm = pe + ca;
            res.pres_nmm = format!("{:.1}", p_nmm);
            res.grupo_4pppp = format_pressure_group(Some(p_nmm));
        }
    }

    res.include_precipitation = data
        .ir
        .as_ref()
        .map(|s| should_include_precipitation(s))
        .unwrap_or(true);
    res.include_weather = data
        .ix
        .as_ref()
        .map(|s| should_include_weather(s))
        .unwrap_or(true);

    res
}

// =============================================================================
// POLÍTICA ÚNICA DE RECÁLCULO — fuente única para todos los call sites
// =============================================================================

/// Campos derivados calculables desde inputs crudos del día.
/// Todos son String porque el frontend los persiste como texto; vacío = no calculable.
#[derive(Debug, Clone, Default)]
pub struct DerivedFields {
    pub tension_vapor: String,
    pub humedad_relativa: String,
    pub punto_rocio: String,
    pub diferencia: String,
    pub pres_nmm: String,
    pub tend_dif: String,
    pub tend_car: String,
    pub visibilidad: String,
    pub tiempo_presente: String,
}

/// Recalcula TODOS los campos derivados desde los valores base de una hora.
///
/// Fuente única — reemplaza las 3 copias previas:
/// - json_handler/synoptic.rs:536-561 (tend/vis/tiempo)
/// - audit/service.rs:145-174 y 264-309 (psicrométricos + pres_nmm via `realizar_calculos`)
/// - monthly_summary (leía `calculado` sin recalcular)
///
/// Política: si un derivado no puede calcularse por falta de inputs, queda vacío
/// y el caller decide si preserva el valor almacenado (compat load) o lo deja vacío.
#[allow(clippy::too_many_arguments)]
pub fn recalculate_derived_fields(
    pool: Option<&DbPool>,
    station_id: Option<&str>,
    ts: Option<&str>,
    th: Option<&str>,
    pres_est: Option<&str>,
    p3: Option<&str>,
    p24: Option<&str>,
    correc_alt: Option<&str>,
    irixhv: Option<&str>,
    seven_ww: Option<&str>,
    nddff_actual: Option<&str>,
    nddff_anterior: Option<&str>,
) -> DerivedFields {
    // Resolver corrección altimétrica: input > pool fallback (misma prioridad que realizar_calculos)
    let mut correc_resolved = correc_alt.unwrap_or("").to_string();
    if correc_resolved.trim().is_empty() {
        if let (Some(sid), Some(p)) = (station_id, pool) {
            if let Some(info) = get_station_info(p, sid) {
                correc_resolved = info.ch.to_string();
            }
        }
    }

    // --- psicrométricos ---
    let ts_val = ts.and_then(|s| s.parse::<f64>().ok());
    let th_val = th.and_then(|s| s.parse::<f64>().ok());
    let mut tension_vapor = String::new();
    let mut humedad_relativa = String::new();
    let mut punto_rocio = String::new();
    let mut diferencia = String::new();

    if let (Some(ts_f), Some(th_f)) = (ts_val, th_val) {
        if th_f <= ts_f {
            if let Some(tv) = calcular_tension_vapor(ts_f, th_f) {
                tension_vapor = format!("{:.1}", tv);
                if let Some(hr) = calcular_humedad_relativa(tv, ts_f) {
                    let hr_c = hr.clamp(0.0, 100.0);
                    humedad_relativa = format!("{:.0}", hr_c);
                    if let Some(pr) = calcular_punto_rocio(ts_f, hr_c) {
                        punto_rocio = format!("{:.1}", pr);
                    }
                }
            }
            diferencia = format!("{:.1}", ts_f - th_f);
        }
    }

    // --- pres_nmm ---
    let mut pres_nmm = String::new();
    if let (Some(pe_s), Ok(ca_f)) = (pres_est, correc_resolved.parse::<f64>()) {
        if let Ok(pe_f) = pe_s.parse::<f64>() {
            pres_nmm = format!("{:.1}", pe_f + ca_f);
        }
    }

    // --- SYNOP derivados ---
    let tend_dif = calc_dif(pres_est.unwrap_or(""), p3.unwrap_or(""));
    let tend_car = calc_car(pres_est.unwrap_or(""), p3.unwrap_or(""));
    let visibilidad = get_visibilidad_from_irixhv(irixhv.unwrap_or(""));
    let tiempo_presente =
        calc_tiempo_presente(seven_ww.unwrap_or(""), nddff_actual.unwrap_or(""), nddff_anterior.unwrap_or(""));

    // p24 solo afecta grupos 58/59 pero no es parte de DerivedFields expuesto al frontend
    // se calcula dentro de realizar_calculos si se necesita; aquí no lo duplicamos.
    let _ = p24; // reservado para futuro grupo 58/59 si se expone

    DerivedFields {
        tension_vapor,
        humedad_relativa,
        punto_rocio,
        diferencia,
        pres_nmm,
        tend_dif,
        tend_car,
        visibilidad,
        tiempo_presente,
    }
}

use std::collections::HashMap;

#[tauri::command]
pub fn get_stations(pool: tauri::State<'_, DbPool>) -> Result<HashMap<String, StationInfo>, String> {
    let stations = stations_repo::get_all_stations(&pool)?;
    let mut map = HashMap::new();
    for st in stations {
        map.insert(st.id.clone(), st);
    }
    Ok(map)
}

#[tauri::command]
pub fn create_station(pool: tauri::State<'_, DbPool>, station: StationInfo) -> Result<(), String> {
    stations_repo::insert_station(&pool, &station)
}

#[tauri::command]
pub fn update_station(pool: tauri::State<'_, DbPool>, station: StationInfo) -> Result<(), String> {
    stations_repo::update_station(&pool, &station)
}

#[tauri::command]
pub fn delete_station(pool: tauri::State<'_, DbPool>, id: String) -> Result<(), String> {
    stations_repo::delete_station(&pool, &id)
}

#[tauri::command]
pub fn calculate_observations(pool: tauri::State<'_, DbPool>, data: CalculationRequest) -> CalculationResponse {
    realizar_calculos(&pool, data)
}
