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
//!
//! MIGRATION TODO:
//! - [ ] move json_handler/synoptic.rs logic here (form <-> JSON mapping)
//! - [ ] move calculations.rs (realizar_calculos + helpers) into calculations/
//! - [ ] the derive-on-load policy must be the ONLY one (today there are 3
//!       copies: synoptic.rs:536-561, audit/service.rs:145-174, 264-309)
//! - [ ] storage (paths, backups, atomic writes) moves to infrastructure::storage;
//!       this module keeps only domain decisions.
//!
//! NOT in scope: station CRUD (infrastructure), auth (modules::auth), CLI sheets.
