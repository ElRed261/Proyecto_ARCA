//! oms_calc — cálculos OMM puros para Neo Arca.
//!
//! REGLA DE ORO: funciones puras (datos entran, resultados salen).
//! Sin archivos, sin SQLite, sin red, sin Qt.
//! Lógica migrada verbatim desde OLD/frontend/src-tauri/src/modules/synoptic/.

use pyo3::prelude::*;

/// Característica `a` de la tendencia barométrica OMM a partir de la
/// diferencia de presión a 3h (`dif`, hPa).
/// Verbatim de `calcular_tendencia_a` (OLD calculations.rs).
#[pyfunction]
fn tendencia_a(dif: f64) -> String {
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

#[pymodule]
fn oms_calc(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(tendencia_a, m)?)?;
    Ok(())
}
