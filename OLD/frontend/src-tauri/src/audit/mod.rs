pub mod commands;
pub mod service;

use serde::Serialize;

#[derive(Serialize)]
pub struct StationInfo {
    pub code: String,
    pub name: String,
}

#[derive(Serialize)]
pub struct DayInfo {
    pub filename: String,
    pub date: String,
    pub observador: String,
    pub horas_registradas: usize,
    pub error_count: i64,
    pub correction_count: i64,
}

// ponytail: single source lives in domain::models — re-export only, no duplication.
pub use crate::domain::models::{AuditObservationData, Correction, ErrorMark, ErrorReportRow, PersonSummaryRow};
