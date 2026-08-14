//! App layer — composition and cross-module orchestration.
//!
//! Scope:
//! - All Tauri `#[tauri::command]` functions converge here as THIN delegates
//!   (today business logic lives in audit/commands.rs and json_handler/*).
//! - Use cases that span modules (e.g. "load day with corrections applied",
//!   "export corrected day") are orchestrated here, calling each module's
//!   public API and domain contracts — NOT inside a module.
//!
//! ## Direction of dependencies
//!
//! ```
//! app (commands/orchestration)
//!   └──> modules (synoptic, cli, auth, monthly_summary, audit)
//!          └──> domain (models, wmo, errors)
//!          └──> infrastructure (storage, db, adapters)
//!                 └──> ports (persistence contracts)
//!                        └──> domain
//! ```
//!
//! The `lib.rs` composition root keeps registering plugins + managed state and
//! delegates command registration to this layer once migration starts.
//!
//! MIGRATION TODO:
//! - [ ] move every #[tauri::command] from modules into thin wrappers here
//! - [ ] move audit FS-browse logic (audit/commands.rs:17-204) into audit's
//!       service, NOT into this layer — this layer orchestrates, it does not
//!       contain business logic either.
