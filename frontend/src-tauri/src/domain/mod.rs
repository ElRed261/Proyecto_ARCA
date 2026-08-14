//! Domain layer — pure shared knowledge, ZERO dependencies on the rest of the crate.
//!
//! This layer owns everything that several modules need and that must never
//! change shape when a module changes:
//!
//! - `errors.rs`  -> AppError (migrate from infrastructure/error.rs)
//! - `models.rs`  -> inter-module data contracts (DayRecord, CliRecord, MonthlyKpis, ...)
//! - `wmo/`       -> single source of truth for WMO tables and SYNOP group encoding
//!                   (visibility, pressure tendency, ww, 1snTTT/4PPPP/... )
//!
//! ## Border rules (HARD)
//!
//! - `domain` must NOT import from: `app`, `modules`, `infrastructure`, `ports`,
//!   `adapters`, `repositories`, or any Tauri type.
//! - Dependencies allowed: only external crates (serde, chrono, thiserror, ...).
//! - If a piece of knowledge belongs to ONE module only, it does NOT go here.
//!   This layer is for shared knowledge and inter-module contracts, nothing else.
//!
//! ## Migration status
//!
//! - [ ] `errors.rs` — move AppError here from infrastructure/error.rs
//! - [ ] `models.rs` — extract DayRecord/HourObservation contracts from json_handler/synoptic.rs
//! - [ ] `wmo/` — consolidate visibility + tendency tables (currently duplicated in
//!       calculations.rs, json_handler/synoptic.rs, cli_autofill.rs) and the ARCA path
//!       convention ("synop" vs "synoptic" vs "Resumen_Mensual_Synop" must become ONE).
