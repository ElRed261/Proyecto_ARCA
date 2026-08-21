# Changelog

All notable changes to Proyecto ARCA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2026-08-21

### Added
- Data pipeline (`pipeline/`): medallion bronze/silver/gold architecture with Google Drive ingestion, pure Excel→JSON transform core, pandera validation (WMO physical ranges), PostgreSQL warehouse with Alembic migrations, idempotent UPSERT by `(station_code, fecha, hora, source_sha256)`
- Orchestration runner (`orchestrate/runner.py`) with Prefect flow fallback, exponential-backoff retries, `last_run.json` observability state
- Query API FastAPI (`api/main.py`): `/health`, `/state`, `/stations/{code}/observations`, `/stations/{code}/kpis`, `/rejected`
- Local file source backend (`ingest/local_source.py`) as Drive stand-in: recursive listing of `.xlsm`/`.xlsx`, atomic copy into `raw/`, selected via `SOURCE_DIR` setting — no Drive connection required
- Modular monolith migration (Fases 1–6): `domain/errors.rs` + `domain/models.rs` single sources, centralized ARCA paths + atomic writes, `modules/synoptic`, `modules/cli`, `modules/auth`, `ports` + `adapters` hexagonal dependency direction (`domain ← ports ← adapters`)
- CI pipeline workflow `.github/workflows/pipeline.yml` (ruff + pytest) alongside existing frontend/backend CI
- Pre-commit hook `scripts/hooks/pre-commit`
- Golden test fixture for Excel transform; integration/wiring/e2e test suites

### Security
- Session tokens now CSPRNG-generated (were hex timestamp+counter); constant-time login miss to prevent user enumeration; expired sessions swept from store
- Deterministic station resolution in `stations_repo`: exact match first, ambiguous suffix → error (was nondeterministic `id LIKE %suffix`)
- Path traversal guard on `monthly_summary` commands via reused `validate_inputs`
- Unique index on `error_marks(fecha, hora, campo, station_id)` closes duplicate-mark race

### Fixed
- Silver/gold UPSERT dialect-aware (sqlite vs postgresql) — was `UnsupportedCompilationError` on the documented Postgres deployment
- Failed files no longer recorded as known checksums — transient DB outages no longer permanently drop files
- SQLite pragmas (`journal_mode=wal`, `foreign_keys=ON`) applied pool-wide via `with_init` (were per-connection)
- Local CLI hour '24' fields survive validation (reverse Z-hour mapping bug dropped them silently)
- Engine config failures raise `RuntimeError` instead of silently falling back to ephemeral `sqlite:///:memory:`

### Removed
- Telegram notification hooks and `TELEGRAM_BOT_TOKEN` setting
- Dead Prefect `@task` wrappers (flow-level retries are what actually executes)

## [2.0.0] - 2026-01-30

### Changed
- Migrated from Electron/PySide6 to Tauri v2 + React 19 + Rust backend
- Consolidated synoptic and CLI observations in Rust native commands
- Implemented SQLite local database with r2d2 connection pool