#![allow(clippy::doc_overindented_list_items)]
//! auth — users, sessions, roles.
//!
//! Scope: login/logout, session store, user CRUD, role checks, password
//! hashing (bcrypt). Does NOT consume domain weather data.
//!
//! MIGRATION TODO:
//! - [ ] move auth.rs here, split: session store / user service / commands
//! - [ ] session tokens: replace predictable timestamp+counter (auth.rs:35-37)
//!       with CSPRNG (uuid v4) — see security audit
//! - [ ] `validate_user_role` (auth.rs:308) is dead — drop it
//! - [ ] error type: converge on domain::errors::AppError
//!
//! BORDER: auth is consumed by the app layer (command wiring) and by other
//! modules ONLY through the role-check contract — never by importing auth
//! internals. Today audit/commands.rs imports auth directly (require_role);
//! that call moves to the app layer during migration.
