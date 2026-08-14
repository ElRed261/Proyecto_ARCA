# Contributing to Proyecto ARCA

## Prerequisites

- **Node.js** 20+ (see `.nvmrc`)
- **Rust** stable toolchain with rustfmt and clippy (see `rust-toolchain.toml`)
- **Linux deps** (for Tauri): `libgtk-3-dev libwebkit2gtk-4.1-dev libjavascriptcoregtk-4.1-dev libsoup-3.0-dev librsvg2-dev`

## Getting Started

```bash
# Clone and install
git clone <repo-url>
cd Proyecto_ARCA
cd frontend && npm install

# Run in development mode
npm run tauri:dev
```

## Branch Policy

- `main` — stable, production-ready
- `ERP-Meteorológico` — active development branch
- Feature branches: `feat/<name>`, `fix/<name>`, `chore/<name>`

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

types: feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert
scopes: audit, auth, cli, db, synoptic, summary, config, frontend, build, ci
```

Examples:
```
feat(audit): add role-based authorization to audit commands
fix(auth): replace forgeable hex token with in-memory SessionStore
refactor(db): add indexes and foreign keys to error_marks and corrections
```

**Never add `Co-Authored-By` or AI attribution to commits.**

## Code Standards

### Rust (Backend)
- Use `Result<T, AppError>` (from `infrastructure/error.rs`) instead of `Result<T, String>`
- Never use `.unwrap()` or `panic!()` in Tauri commands — return `Result`
- Document public functions and commands with `///` doc comments
- Follow the Hexagonal Architecture pattern (see `monthly_summary/` as template)
- Use `State<DbPool>` for database access — never `Connection::open` directly

### React (Frontend)
- Use TypeScript (migration in progress — new files should be `.tsx`)
- Use the centralized `normalizeRole`/`hasRole` from `shared/utils/auth.js` for role checks
- Use Tauri's native `@tauri-apps/plugin-dialog` for confirmations — never `window.confirm`
- Follow feature-first organization under `frontend/src/features/`
- No god components — target max 250 LOC per page

### Testing
- Rust: `cargo test` (tests in `#[cfg(test)]` modules)
- Frontend: `npm run lint` + `npm run build` (Vitest pending)
- CI must pass before merge: `cargo check`, `cargo clippy -- -D warnings`, `cargo test`, `npm run lint`, `npm run build`

## Architecture

This project follows a Hexagonal Architecture (Ports & Adapters) pattern adapted to Tauri:

```
src-tauri/src/
├── commands/        ← IPC layer (thin, delegates to services)
├── domain/          ← Pure business logic (no I/O)
├── ports/           ← Trait definitions (abstractions)
├── adapters/        ← Concrete implementations (SQLite, JSON files)
├── infrastructure/  ← DB pool, error types, config, migrations
└── monthly_summary/ ← Reference implementation (follow this pattern)
```

## Security Guidelines

- All Tauri commands that modify data MUST call `require_role()` with the appropriate roles
- Never accept `marcado_por`, `corregido_por`, or similar identity fields from the frontend — always derive from `session.email`
- Validate all file paths with `validate_safe_path()` or `validate_inputs()` — never accept arbitrary paths
- Never hardcode credentials in source code — use the first-run random generation pattern