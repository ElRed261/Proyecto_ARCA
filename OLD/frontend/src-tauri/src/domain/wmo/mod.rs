//! WMO tables and SYNOP group encoding — single source of truth.
//!
//! Today the same domain knowledge is copy-pasted in 3+ places:
//!
//! - visibility:  cli_autofill.rs:23-103 (80-line HashMap) vs json_handler/synoptic.rs:103-130
//! - tendency:    calculations.rs:91-129 (`calcular_tendencia_a`) vs json_handler/synoptic.rs:161-183 (`calc_car`)
//! - ww/tiempo:   cli_autofill.rs:136-153 vs json_handler/synoptic.rs:186-210
//! - paths:       "synop" vs "synoptic" vs "Resumen_Mensual_Synop" conventions
//!
//! MIGRATION TODO: consolidate everything here as pure functions + const tables,
//! with unit tests, and delete the duplicates. cli_autofill.rs is dead code
//! (registered in lib.rs but never called by the frontend) — drop it, do not move it.
