//! synoptic — day of observation.
//!
//! Scope: WMO synoptic form logic, meteorological calculations for the day,
//! and the day JSON file (produce/persist/load DayRecord).
//!
//! PRODUCES: `DayRecord` (contract in domain/models.rs) persisted by
//! infrastructure::storage under the ARCA path convention.
//!
//! CONSUMERS: modules::cli (autofill), modules::monthly_summary (KPIs),
//! modules::audit (review), app layer (export).

pub mod calculations;
pub mod storage;

// Re-exports for external call sites that still import via json_handler/calculations paths
pub use calculations::{
    calc_car, calc_dif, calc_tiempo_presente, format_dif, get_prev_hour,
    get_visibilidad_from_irixhv, recalculate_derived_fields, to_frontend_name, to_synop_name,
    DerivedFields,
};
pub use storage::{get_observation, get_observation_core, get_station_date_range, save_observation_json, save_observation_json_core};
