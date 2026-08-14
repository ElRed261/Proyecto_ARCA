//! cli — CLI 3074 / 4074 / 5074 sheets.
//!
//! Scope: the three CLI forms (pressure/humidity/wind, cloudiness/temperature,
//! significant phenomena), their autofill logic and their persistence.
//!
//! CONSUMES: `DayRecord` from modules::synoptic (autofill from the saved
//! synoptic observation: temperatures, pressures, extremes).
//!
//! PRODUCES: `CliRecord` embedded in the day file (contract in domain/models.rs).
//!
//! MIGRATION TODO:
//! - [ ] move json_handler/cli.rs here (save_cli3074/4074/5074_json, load_*)
//! - [ ] cli_autofill.rs is DEAD (registered in lib.rs:27, zero frontend callers)
//!       and duplicates WMO tables — delete it, do not migrate it
//! - [ ] the WMO tables it needs move to domain/wmo (single source of truth)
//!
//! DEPENDENCY RULE: this module may read DayRecord via the contract, never via
//! json_handler internals.
