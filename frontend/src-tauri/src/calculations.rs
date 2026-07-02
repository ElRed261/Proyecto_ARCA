use crate::db::DbPool;
use serde::{Deserialize, Serialize};
use crate::repositories::stations_repo::{self, StationInfo};

pub fn get_station_info(pool: &DbPool, station_id: &str) -> Option<StationInfo> {
    stations_repo::get_station_by_id(pool, station_id).unwrap_or(None)
}

// =============================================================================
// CÁLCULOS METEOROLÓGICOS
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tension_vapor() {
        let ts = 25.0;
        let th = 20.0;
        let tv = calcular_tension_vapor(ts, th).unwrap();
        assert!((tv - 19.3).abs() < 1.0, "Tensión de vapor inválida: {}", tv);
    }

    #[test]
    fn test_humedad_relativa() {
        let ts = 25.0;
        let tv = 19.3;
        let hr = calcular_humedad_relativa(tv, ts).unwrap();
        assert!(hr > 50.0 && hr < 70.0, "Humedad relativa inválida: {}", hr);
    }

    #[test]
    fn test_punto_rocio() {
        let ts = 25.0;
        let hr = 60.0;
        let pr = calcular_punto_rocio(ts, hr).unwrap();
        assert!((pr - 16.7).abs() < 2.0, "Punto de rocío inválido: {}", pr);
    }

    #[test]
    fn test_tendencia_a() {
        assert_eq!(calcular_tendencia_a(0.0), "4");
        assert_eq!(calcular_tendencia_a(0.3), "0");
        assert_eq!(calcular_tendencia_a(1.0), "1");
        assert_eq!(calcular_tendencia_a(1.8), "2");
        assert_eq!(calcular_tendencia_a(2.5), "3");
        assert_eq!(calcular_tendencia_a(-0.3), "5");
        assert_eq!(calcular_tendencia_a(-1.0), "6");
        assert_eq!(calcular_tendencia_a(-1.8), "7");
        assert_eq!(calcular_tendencia_a(-2.5), "8");
    }

    #[test]
    fn test_format_temperature_group() {
        assert_eq!(format_temperature_group(Some(25.4)), "10254");
        assert_eq!(format_temperature_group(Some(-5.2)), "11052");
        assert_eq!(format_temperature_group(None), "");
    }

    #[test]
    fn test_format_dew_point_group() {
        assert_eq!(format_dew_point_group(Some(16.7)), "20167");
        assert_eq!(format_dew_point_group(Some(-3.4)), "21034");
        assert_eq!(format_dew_point_group(None), "");
    }

    #[test]
    fn test_format_pressure_group() {
        assert_eq!(format_pressure_group(Some(1015.3)), "40153");
        assert_eq!(format_pressure_group(Some(998.4)), "49984");
        assert_eq!(format_pressure_group(None), "");
    }
}
