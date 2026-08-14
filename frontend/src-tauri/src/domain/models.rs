//! Inter-module data contracts — the ONLY way modules exchange domain data.
//!
//! Modules that work in sequence (synoptic -> cli -> monthly_summary -> audit)
//! must NOT import each other. They consume each other's output through these
//! contracts (and through the day JSON file persisted by infrastructure/storage).
//!
//! MIGRATION TODO: extract these from the current code:
//!
//! - `DayRecord`      — the day of observation as persisted (meta + horas wrapper).
//!                      Today it is an implicit, unversioned JSON shape in
//!                      json_handler/synoptic.rs. It becomes an explicit struct
//!                      WITH a `schema_version` field so old files can be migrated.
//! - `HourObservation`— one hour block (datos + synop + calculado).
//! - `CliRecord`      — cli3074/cli4074/cli5074 payload (embedded in the day file).
//! - `MonthlyKpis`    — output of modules::monthly_summary consumed by the UI/export.
//! - `AuditMark` / `Correction` — owned by modules::audit but defined here because
//!                      ports/adapters (infrastructure) must reference them WITHOUT
//!                      importing the audit module (fixes the current inverted
//!                      dependency in ports/mod.rs).
//!
//! ## Contract rules
//!
//! - Serde derives live here so every module serializes the SAME shape.
//! - No Tauri types, no rusqlite types in this file.
