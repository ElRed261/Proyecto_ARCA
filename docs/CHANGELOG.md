# Changelog

All notable changes to Proyecto ARCA will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.0] - 2026-10-12

### Added
- Configurable save paths (P1): central `PathProfile` (offline root / online Drive Desktop folder / backups age / summaries dir) persisted in `app_config`, admin-gated `set_path_config`, real `probe_path` writes test; resolution chain `ARCA_BASE_DIR > profile > Documents/ARCA` wired into every reader and writer
- Dual-destination sync engine (P3): offline-first saves copy to the online folder when available; failures enqueue into `sync_pending` with honest backoff (`2^attempts` minutes, capped 60); manual force retry (`Reintentar ahora`); `get_sync_status` aggregate; sha256 dedupe avoids re-sending identical content; success marks stale pending rows synced
- Robust save pipeline (P2): per-file exclusive locks (stale-lock theft), fsync atomic writes (temp + sync_all + rename), `schema_version: 1` injected at every document root, structured save errors `{stage, path, detail}`, backup retention with sha256 dedupe + age pruning + byte cap
- Admin Settings page replacing the maintenance stub: path cards with directory picker and inline probe errors, sync panel (pending/synced counts, last 5 errors, force retry) for every authenticated user, one-shot idempotent legacy month-dir migration command
- Observer safeguards: synoptic draft autosaved on every change bound to (station, fecha) with metadata validation, `beforeunload` guard, structured save errors surfaced in toasts, day change keeps the active hour and no longer shows a native `window.confirm`
- SYNOP group validation (server-side): meteo_*/extra_* fields capped at 5 chars, digits and `/` only
- One-command dev launcher `./run.sh` with environment prerequisite checks

### Changed
- `audit_browse_months` is a pure read now (legacy Spanish month dirs shown numerically, never renamed during listing)
- Station codes normalized to lowercase on every filesystem key (Windows/macOS case-collision safety)
- Invalid dates hard-fail in save/read paths (no more silent 2025/12 fallback); calendar-true validation incl. leap February
- Windows Documents fallback fixed (data no longer escapes to `C:\Users\X\ARCA`); `Resumen_Mensual` under the unified resolution chain
- README rewritten without emojis, with committed colored Lucide SVG icons; documented sync/pipeline/settings

### Security
- Same-second backup-name collision fixed (backups used to silently overwrite each other; now millisecond timestamps + duplicate-path guard)

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