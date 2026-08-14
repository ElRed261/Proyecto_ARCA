# Changelog

All notable changes to Proyecto ARCA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Replaced forgeable hex token with in-memory `SessionStore` (session-based auth with 8h expiry)
- Added `require_role()` authorization to all sensitive Tauri commands (delete_user, change_password, audit_propose_correction, audit_mark_error, audit_export_corrected_json)
- Bound `marcado_por` / `corregido_por` to authenticated session email (no longer accepted from frontend)
- Added `validate_safe_path()` and `validate_export_path()` to prevent path traversal in monthly_summary commands
- Added `validate_inputs()` to `audit_export_corrected_json` for station_id sanitization
- Removed hardcoded credentials from `db.rs` — now generates random passwords on first run
- Removed credentials from `run_full.sh`
- Added `RoleRoute` in frontend to protect `/admin` and `/audit` routes by role

### Architecture
- Created `ports/` module with `UserRepository` and `AuditRepository` traits
- Created `adapters/` with `SqliteUserRepository` and `SqliteAuditRepository`
- Created `infrastructure/error.rs` with `AppError` enum (thiserror)
- Refactored `audit.rs` to use `AuditRepository` trait (reduced from 1121 to ~962 LOC)

### Database
- Added `PRAGMA foreign_keys=ON`
- Added indexes on `error_marks(station_id, fecha)`, `corrections(station_id, fecha)`, `summary_logs(station_id, year, month)`
- Removed dead tables: `audit_logs`, `correction_requests`
- Added foreign keys: `station_id REFERENCES stations(id)`

### Build & CI
- Pinned Tauri versions (Rust crate 2.11.3, npm @tauri-apps/api 2.11.1)
- Removed `lazy_static` dependency (unused)
- Removed `features = ["test"]` from tauri in Cargo.toml
- Added `[profile.release]` with LTO, strip, codegen-units=1, panic=abort
- Created `.github/workflows/ci.yml` with cargo check, cargo test, cargo clippy, npm lint, npm build
- Added `.nvmrc` (Node 20) and `rust-toolchain.toml` (stable + rustfmt + clippy)

### Cleanup
- Moved legacy Python backend to `miscelaneos/backend_python/`
- Removed `axios` dependency and `axiosConfig.js` (dead code — frontend uses Tauri IPC)
- Removed sensitive files from git tracking (arca_local.db, *.log, *.bak, observation data)
- Fixed `.gitignore` (split concatenated patterns, added missing entries)
- Added `LICENSE` (CC BY-NC-SA-4.0)
- Added `CONTRIBUTING.md`
- Added this `CHANGELOG.md`

### Frontend
- Centralized role normalization in `shared/utils/auth.js` (`normalizeRole`, `hasRole`, `normalizeRoles`)
- Fixed role type bug (string vs object) across 6 components (DashboardPage, AdminPage, SummaryPage, AuditObservationPage, App.jsx)

## [2.0.0] - 2026-01-30

### Changed
- Migrated from Electron/PySide6 to Tauri v2 + React 19 + Rust backend
- Consolidated synoptic and CLI observations in Rust native commands
- Implemented SQLite local database with r2d2 connection pool