//! Inter-module data contracts — the ONLY way modules exchange domain data.
//!
//! Modules that work in sequence (synoptic -> cli -> monthly_summary -> audit)
//! must NOT import each other. They consume each other's output through these
//! contracts (and through the day JSON file persisted by infrastructure/storage).
//!
//! MIGRATION TODO: extract these from the current code:
//!
//! - `DayRecord`      — the day of observation as persisted (meta + horas wrapper).
//!   Today it is an implicit, unversioned JSON shape in
//!   json_handler/synoptic.rs. It becomes an explicit struct
//!   WITH a `schema_version` field so old files can be migrated.
//! - `HourObservation`— one hour block (datos + synop + calculado).
//! - `CliRecord`      — cli3074/cli4074/cli5074 payload (embedded in the day file).
//! - `MonthlyKpis`    — output of modules::monthly_summary consumed by the UI/export.
//! - `AuditMark` / `Correction` — owned by modules::audit but defined here because
//!   ports/adapters (infrastructure) must reference them WITHOUT
//!   importing the audit module (fixes the current inverted
//!   dependency in ports/mod.rs).
//!
//! ## Contract rules
//!
//! - Serde derives live here so every module serializes the SAME shape.
//! - No Tauri types, no rusqlite types in this file.

use serde::{Deserialize, Serialize};

// ponytail: single source of truth for audit domain types — audit re-exports from here, ports/adapters depend only on domain.

#[derive(Serialize, Deserialize, Clone)]
pub struct ErrorMark {
    pub id: Option<i32>,
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub tipo_error: String,
    pub nota: Option<String>,
    pub marcado_por: String,
    pub created_at: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Correction {
    pub id: Option<i32>,
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub valor_original: String,
    pub valor_corregido: String,
    pub justificacion: String,
    pub corregido_por: String,
    pub aprobado_por: Option<String>,
    pub estado: String,
    pub created_at: Option<String>,
}

#[derive(Serialize)]
pub struct AuditObservationData {
    pub observation: serde_json::Value,
    pub error_marks: Vec<ErrorMark>,
    pub corrections: Vec<Correction>,
}

#[derive(Serialize)]
pub struct ErrorReportRow {
    pub error_id: i32,
    pub station_id: String,
    pub fecha: String,
    pub hora: String,
    pub campo: String,
    pub tipo_error: String,
    pub nota: Option<String>,
    pub marcado_por: String,
    pub valor_original: Option<String>,
    pub valor_corregido: Option<String>,
    pub justificacion: Option<String>,
    pub corregido_por: Option<String>,
    pub estado: Option<String>,
    pub created_at: String,
}

#[derive(Serialize)]
pub struct PersonSummaryRow {
    pub persona: String,
    pub errores_marcados: i64,
    pub correcciones_propuestas: i64,
    pub correcciones_aprobadas: i64,
}
