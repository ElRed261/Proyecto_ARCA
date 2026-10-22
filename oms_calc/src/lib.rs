//! oms_calc — cálculos OMM puros para Neo Arca.
//!
//! REGLA DE ORO: funciones puras (datos entran, resultados salen).
//! Sin archivos, sin SQLite, sin red, sin Qt.
//! Lógica migrada verbatim desde OLD/frontend/src-tauri/src/{modules/synoptic,monthly_summary}/.

mod monthly;
mod synoptic;

#[cfg(test)]
mod tests_monthly;
#[cfg(test)]
mod tests_synoptic;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use monthly::{process_day_data, DailyObservation};
use synoptic::{
    calc_car as rs_calc_car, calc_dif as rs_calc_dif, calc_tiempo_presente as rs_calc_tiempo_presente,
    calcular_h26 as rs_h26, calcular_h27 as rs_h27, calcular_h28_asumido as rs_h28_asumido,
    calcular_humedad_relativa as rs_humedad_relativa, calcular_punto_rocio as rs_punto_rocio,
    calcular_tendencia_a as rs_tendencia_a, calcular_tension_vapor as rs_tension_vapor,
    format_dew_point_group as rs_format_dew_point_group, format_dif as rs_format_dif,
    format_humidity_group as rs_format_humidity_group,
    format_pressure_24h_group as rs_format_pressure_24h_group,
    format_pressure_group as rs_format_pressure_group,
    format_pressure_tendency_group as rs_format_pressure_tendency_group,
    format_temperature_group as rs_format_temperature_group, get_prev_hour as rs_get_prev_hour,
    get_visibilidad_from_irixhv as rs_get_visibilidad_from_irixhv,
    realizar_calculos_puro as rs_realizar_calculos_puro,
    recalculate_derived_fields as rs_recalculate_derived_fields,
    should_include_precipitation as rs_should_include_precipitation,
    should_include_weather as rs_should_include_weather, to_frontend_name as rs_to_frontend_name,
    to_synop_name as rs_to_synop_name,
};

/// Característica `a` de la tendencia barométrica OMM a partir de la
/// diferencia de presión a 3h (`dif`, hPa).
/// Verbatim de `calcular_tendencia_a` (OLD calculations.rs).
#[pyfunction]
fn tendencia_a(dif: f64) -> String {
    rs_tendencia_a(dif)
}

// =============================================================================
// Psychrometric helpers (plain types; Option<f64> maps to Optional[float])
// =============================================================================

/// Saturation vapor pressure (hPa) over water at the wet-bulb temperature.
#[pyfunction]
fn calcular_h26(temp_humedo: f64) -> Option<f64> {
    rs_h26(temp_humedo)
}

/// Psychrometric coefficient term.
#[pyfunction]
fn calcular_h27(temp_humedo: f64) -> f64 {
    rs_h27(temp_humedo)
}

/// Saturation vapor pressure (hPa) at the dry-bulb temperature (h28 assumed).
#[pyfunction]
fn calcular_h28_asumido(temp_seco: f64) -> Option<f64> {
    rs_h28_asumido(temp_seco)
}

/// Vapor tension (hPa) from dry/wet bulb temperatures.
#[pyfunction]
fn calcular_tension_vapor(temp_seco: f64, temp_humedo: f64) -> Option<f64> {
    rs_tension_vapor(temp_seco, temp_humedo)
}

/// Relative humidity (%) from vapor tension and dry-bulb temperature.
#[pyfunction]
fn calcular_humedad_relativa(tension_vapor: f64, temp_seco: f64) -> Option<f64> {
    rs_humedad_relativa(tension_vapor, temp_seco)
}

/// Dew point (°C) from dry-bulb temperature and relative humidity (%).
#[pyfunction]
fn calcular_punto_rocio(temp_seco: f64, humedad_relativa_porc: f64) -> Option<f64> {
    rs_punto_rocio(temp_seco, humedad_relativa_porc)
}

// =============================================================================
// SYNOP group formatters
// =============================================================================

/// Group `1snTTT` (dry-bulb temperature).
#[pyfunction]
fn format_temperature_group(temp: Option<f64>) -> String {
    rs_format_temperature_group(temp)
}

/// Group `2snTdTdTd` (dew point).
#[pyfunction]
fn format_dew_point_group(dew_point: Option<f64>) -> String {
    rs_format_dew_point_group(dew_point)
}

/// Group `4PPPP` (pressure at mean sea level).
#[pyfunction]
fn format_pressure_group(pressure: Option<f64>) -> String {
    rs_format_pressure_group(pressure)
}

/// Group `5apPP` (pressure tendency at 3h).
#[pyfunction]
fn format_pressure_tendency_group(diferencia_p3: Option<f64>) -> String {
    rs_format_pressure_tendency_group(diferencia_p3)
}

/// Group `58/59pPP` (pressure variation at 24h).
#[pyfunction]
fn format_pressure_24h_group(diferencia_p24: Option<f64>) -> String {
    rs_format_pressure_24h_group(diferencia_p24)
}

/// Group `29UUU` (relative humidity).
#[pyfunction]
fn format_humidity_group(humedad_relativa: Option<f64>) -> String {
    rs_format_humidity_group(humedad_relativa)
}

// =============================================================================
// Include policies and WMO mappings
// =============================================================================

/// Group 6RRRtr is included only for IR in {0, 1, 2}.
#[pyfunction]
fn should_include_precipitation(ir: &str) -> bool {
    rs_should_include_precipitation(ir)
}

/// Present-weather group is included for IX in {1, 4, 7} (Table 1860).
#[pyfunction]
fn should_include_weather(ix: &str) -> bool {
    rs_should_include_weather(ix)
}

/// Frontend field name -> SYNOP group name (verbatim table).
#[pyfunction]
fn to_synop_name(frontend_name: &str) -> String {
    rs_to_synop_name(frontend_name)
}

/// SYNOP group name -> frontend field name (verbatim table).
#[pyfunction]
fn to_frontend_name(synop_name: &str) -> String {
    rs_to_frontend_name(synop_name)
}

/// Visibility (km, table value) from the last two digits of `IrIXhVV`.
#[pyfunction]
fn get_visibilidad_from_irixhv(irixhv: &str) -> String {
    rs_get_visibilidad_from_irixhv(irixhv)
}

/// Insert the decimal point in a `dif` string exactly like the oracle does.
#[pyfunction]
fn format_dif(dif_value: &str) -> String {
    rs_format_dif(dif_value)
}

/// |pres_est - p3| formatted with 1 decimal (zero-padded, width 4).
#[pyfunction]
fn calc_dif(pres_est: &str, p3: &str) -> String {
    rs_calc_dif(pres_est, p3)
}

/// OMM characteristic `a` from pres_est - p3 (no rounding; raw difference).
#[pyfunction]
fn calc_car(pres_est: &str, p3: &str) -> String {
    rs_calc_car(pres_est, p3)
}

/// Present weather (`ww`) with fallback on the Nddff cloud-cover evolution.
#[pyfunction]
fn calc_tiempo_presente(seven_ww: &str, nddff_current: &str, nddff_prev: &str) -> String {
    rs_calc_tiempo_presente(seven_ww, nddff_current, nddff_prev)
}

/// Previous synoptic hour in the 03/06/09/12/15/18/21/00Z chain ("" if unknown).
#[pyfunction]
fn get_prev_hour(hora: &str) -> String {
    rs_get_prev_hour(hora).to_string()
}

// =============================================================================
// JSON boundary — CalculationRequest/Response cross as JSON strings
// =============================================================================

/// Pure core of the oracle `realizar_calculos` over the JSON boundary.
///
/// `request_json` is a serialized CalculationRequest (the station echo may ride
/// inside it under the `station_info` key); `correc_alt` is the station fallback
/// resolved by Python from the stations repository (F4), mirroring the pool
/// lookup the oracle performed. Malformed JSON raises ValueError.
#[pyfunction]
fn realizar_calculos_json(request_json: &str, correc_alt: Option<&str>) -> PyResult<String> {
    let data: synoptic::CalculationRequest =
        serde_json::from_str(request_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let res = rs_realizar_calculos_puro(data, correc_alt.map(|s| s.to_string()));
    serde_json::to_string(&res).map_err(|e| PyValueError::new_err(e.to_string()))
}

/// Pure core of the oracle `recalculate_derived_fields` over the JSON boundary.
/// Returns the serialized DerivedFields JSON. `correc_alt_resuelta` is the
/// station fallback the oracle obtained from the pool; Python resolves it (F4).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn recalculate_derived_fields_json(
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
    correc_alt_resuelta: Option<&str>,
) -> String {
    let derived = rs_recalculate_derived_fields(
        station_id,
        ts,
        th,
        pres_est,
        p3,
        p24,
        correc_alt,
        irixhv,
        seven_ww,
        nddff_actual,
        nddff_anterior,
        correc_alt_resuelta,
    );
    serde_json::to_string(&derived).unwrap_or_default()
}

/// Daily KPIs from a serialized DailyObservation (monthly_summary pipeline).
/// Malformed JSON raises ValueError.
#[pyfunction]
fn process_day_data_json(obs_json: &str) -> PyResult<String> {
    let obs: DailyObservation =
        serde_json::from_str(obs_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
    let kpis = process_day_data(&obs);
    serde_json::to_string(&kpis).map_err(|e| PyValueError::new_err(e.to_string()))
}

#[pymodule]
fn oms_calc(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(tendencia_a, m)?)?;
    m.add_function(wrap_pyfunction!(calcular_h26, m)?)?;
    m.add_function(wrap_pyfunction!(calcular_h27, m)?)?;
    m.add_function(wrap_pyfunction!(calcular_h28_asumido, m)?)?;
    m.add_function(wrap_pyfunction!(calcular_tension_vapor, m)?)?;
    m.add_function(wrap_pyfunction!(calcular_humedad_relativa, m)?)?;
    m.add_function(wrap_pyfunction!(calcular_punto_rocio, m)?)?;
    m.add_function(wrap_pyfunction!(format_temperature_group, m)?)?;
    m.add_function(wrap_pyfunction!(format_dew_point_group, m)?)?;
    m.add_function(wrap_pyfunction!(format_pressure_group, m)?)?;
    m.add_function(wrap_pyfunction!(format_pressure_tendency_group, m)?)?;
    m.add_function(wrap_pyfunction!(format_pressure_24h_group, m)?)?;
    m.add_function(wrap_pyfunction!(format_humidity_group, m)?)?;
    m.add_function(wrap_pyfunction!(should_include_precipitation, m)?)?;
    m.add_function(wrap_pyfunction!(should_include_weather, m)?)?;
    m.add_function(wrap_pyfunction!(to_synop_name, m)?)?;
    m.add_function(wrap_pyfunction!(to_frontend_name, m)?)?;
    m.add_function(wrap_pyfunction!(get_visibilidad_from_irixhv, m)?)?;
    m.add_function(wrap_pyfunction!(format_dif, m)?)?;
    m.add_function(wrap_pyfunction!(calc_dif, m)?)?;
    m.add_function(wrap_pyfunction!(calc_car, m)?)?;
    m.add_function(wrap_pyfunction!(calc_tiempo_presente, m)?)?;
    m.add_function(wrap_pyfunction!(get_prev_hour, m)?)?;
    m.add_function(wrap_pyfunction!(realizar_calculos_json, m)?)?;
    m.add_function(wrap_pyfunction!(recalculate_derived_fields_json, m)?)?;
    m.add_function(wrap_pyfunction!(process_day_data_json, m)?)?;
    Ok(())
}
