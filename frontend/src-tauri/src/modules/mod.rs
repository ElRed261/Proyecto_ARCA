//! Domain modules — the modular monolith. Each module is an independent domain
//! slice. The DIRECTORY of a module is its boundary; nothing outside it may
//! reach into its internals.
//!
//! Declared modules:
//!
//! - `synoptic`         — day of observation: form logic, calculations, day JSON.
//!                        PRODUCES DayRecord. (migrate from json_handler/synoptic.rs
//!                        + calculations.rs)
//! - `cli`              — CLI 3074/4074/5074. CONSUMES DayRecord (autofill).
//!                        (migrate from json_handler/cli.rs; drop cli_autofill.rs)
//! - `auth`             — users, sessions, roles. Does NOT consume domain data.
//!                        (migrate from auth.rs)
//! - `monthly_summary`  — ALREADY ESTABLISHED at src/monthly_summary/. Self-contained,
//!                        the reference pattern. CONSUMES day files (synoptic+cli).
//! - `audit`            — ALREADY ESTABLISHED at src/audit/. CONSUMES day files +
//!                        DB marks/corrections.
//!
//! ## Border rules (HARD)
//!
//! 1. A domain module NEVER imports another domain module. Sequence between
//!    modules flows through the data contracts in `domain/models.rs` and the
//!    day JSON files on disk (via infrastructure::storage).
//! 2. `modules` -> `domain` (contracts) and `infrastructure` (storage/db) is allowed.
//! 3. `domain` and `infrastructure` NEVER import `modules`.
//! 4. Cross-module use cases (e.g. "export corrected day") are orchestrated in
//!    the `app` layer, NOT inside a module.
//!
//! MIGRATION NOTE: modules/* are NOT declared in lib.rs yet. The current tree
//! (json_handler/, auth.rs, calculations.rs, ...) keeps compiling untouched.
//! Each module migrates one at a time, keeping the build green.
