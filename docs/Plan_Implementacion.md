# Plan de Implementación Riguroso — Proyecto ARCA

**Fecha:** Junio 2026
**Objetivo:** Llevar el proyecto a estándar profesional, ejecutable y funcional
**Baseline:** Backend Rust compila, Frontend compila, Tauri build FALLA (version mismatch)

---

## Fase 0 — Estabilizar el Build (prerrequisito)

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 0.1 | Fix version mismatch Tauri: alinear `@tauri-apps/api` npm con crate Rust | `npx tauri build --debug` completa sin error de version mismatch |
| 0.2 | Eliminar `lazy_static` de Cargo.toml (dependencia zombi) | `cargo check` pasa sin lazy_static |
| 0.3 | Eliminar `features = ["test"]` de tauri en Cargo.toml | `cargo check` pasa |
| 0.4 | Agregar `[profile.release]` con lto, strip, codegen-units=1 | `cargo build --release` produce binario optimizado |

**Verificación de fase:** `npx tauri build --debug` completa exitosamente.

---

## Fase 1 — Seguridad Crítica

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 1.1 | Reemplazar token hex forgeable por sesión in-memory (SessionStore ya existe en lib.rs:20) | `auth.rs` no genera token hex; login usa SessionStore |
| 1.2 | Implementar `validate_user_role` en comandos sensibles (delete_user, change_password, audit_propose_correction, audit_mark_error) | grep confirma llamadas a validate_user_role en cada comando sensible |
| 1.3 | Validar paths en `ms_delete_summary`, `ms_export_excel`, `ms_load_summary`: canonicalizar y verificar dentro de base dir | Comandos rechazan paths con `..` o fuera de base dir |
| 1.4 | Validar `station_id` con `validate_inputs` en `audit_export_corrected_json` | Comando rechaza station_id inválido |
| 1.5 | Binding de `marcado_por`/`corregido_por` al usuario autenticado server-side (no del frontend) | Campos se obtienen de SessionStore, no del payload |
| 1.6 | Eliminar credenciales hardcodeadas de `db.rs`: generar password random en first-run, forzar cambio | No hay passwords en código fuente; first-run genera random |
| 1.7 | Eliminar credenciales de `run_full.sh` | No hay passwords en run_full.sh |
| 1.8 | Frontend: ProtectedRoute con roles (`<RoleRoute roles={['admin']}>`) | `/admin` y `/audit` rechazan usuarios sin rol |
| 1.9 | Fix bug de tipos en roles: centralizar string|object en un solo lugar | No hay llamadas a `r.toLowerCase()` sin normalización previa |

**Verificación de fase:** `cargo check` + `npm run build` pasan; revisión manual confirma fixes de seguridad.

---

## Fase 2 — Limpieza y Git Hygiene

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 2.1 | Eliminar `backend/` completo (Python muerto) | `backend/` no existe |
| 2.2 | Eliminar `frontend/src/shared/api/axiosConfig.js` + `axios` de package.json | `axios` no está en package.json ni en bundle |
| 2.3 | Arreglar `.gitignore`: split línea 18, agregar `*.log`, `*.db`, `*.bak`, `__pycache__/`, `.venv/`, `*.xlsm` | .gitignore tiene patrones en líneas separadas |
| 2.4 | `git rm --cached` de: backend.log, frontend.log, scratch/__pycache__/, docs/*.pdf, docs/*.xlsm | Archivos sensibles fuera de git tracking |
| 2.5 | Eliminar `scratch/` del repo | scratch/ no está en git |
| 2.6 | Sincronizar versiones: un source of truth en tauri.conf.json | package.json, Cargo.toml, README coinciden |
| 2.7 | Agregar `LICENSE` (MIT o Apache-2.0) | LICENSE existe en raiz |
| 2.8 | Agregar `rust-toolchain.toml` + `.nvmrc` | Archivos existen |

**Verificación de fase:** `git status` limpio; `cargo check` + `npm run build` pasan.

---

## Fase 3 — Arquitectura Backend

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 3.1 | Completar refactor `audit.rs` usando adapters/ports existentes | audit.rs delega a AuditRepository trait |
| 3.2 | Completar refactor `auth.rs` usando UserRepository trait | auth.rs delega a UserRepository trait |
| 3.3 | Reemplazar `Result<T, String>` con `Result<T, AppError>` en comandos | grep confirma cero `Result<T, String>` en comandos nuevos |
| 3.4 | De-duplicar CLI: colapsar save_cli3074/4074/5074 en `save_cli_json(key)` | cli.rs tiene 1 función genérica en lugar de 3 |
| 3.5 | Unificar tabla visibilidad en una sola `const VIS_TABLE` | Una sola fuente de verdad |
| 3.6 | Fix N+1 en `audit_browse_days`: GROUP BY en lugar de 2 COUNT por archivo | 1 query en lugar de 62 |
| 3.7 | Hacer `init_db` fatal si falla (no tragar error) | App panica si DB no inicializa |

**Verificación de fase:** `cargo check` + `cargo test` pasan.

---

## Fase 4 — Database

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 4.1 | Agregar `PRAGMA foreign_keys=ON` tras abrir pool | FKs se enforcean |
| 4.2 | Agregar índices: error_marks(station_id, fecha), corrections(station_id, fecha), summary_logs(station_id, year, month) | CREATE INDEX existe en db.rs |
| 4.3 | Agregar FKs: station_id REFERENCES stations(id) en error_marks, corrections, summary_logs | Schema tiene FKs |
| 4.4 | Borrar tablas muertas: audit_logs, correction_requests | Tablas no existen en schema |
| 4.5 | Mover pool consistente: todos los comandos usan State<DbPool> | grep confirma cero `Connection::open` en comandos |

**Verificación de fase:** `cargo check` + `cargo test` pasan; DB inicializa sin errores.

---

## Fase 5 — Frontend

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 5.1 | Eliminar dead code: axiosConfig.js, SynopticSidebar.jsx (no usado) | Archivos no existen |
| 5.2 | Centralizar normalización de roles en `shared/utils/auth.js` | Una sola función `normalizeRole(r)` |
| 5.3 | ProtectedRoute con roles | `/admin` rechaza no-admin |
| 5.4 | Fix `<html lang="es">` en index.html | index.html tiene lang="es" |
| 5.5 | Accesibilidad básica: aria-label en botones icono, divs onClick -> button | grep `aria-label` tiene resultados |

**Verificación de fase:** `npm run build` + `npm run lint` pasan.

---

## Fase 6 — CI/CD y Testing

| # | Tarea | Criterio de verificación |
|---|-------|--------------------------|
| 6.1 | Crear `.github/workflows/ci.yml` con cargo test, cargo clippy, npm run lint, npm run build | Workflow existe y se ejecuta |
| 6.2 | Agregar Dependabot config | .github/dependabot.yml existe |
| 6.3 | Tests Rust para auth.rs (login success/fail) | cargo test pasa con nuevos tests |
| 6.4 | Agregar CONTRIBUTING.md + CHANGELOG.md | Archivos existen |

**Verificación de fase:** CI workflow ejecuta sin errores.

---

## Reglas de Ejecución

1. **Cada fase debe dejar el programa compilable y ejecutable**
2. **Verificar después de cada tarea:** `cargo check` + `npm run build`
3. **Si una tarea rompe el build, se fixea antes de avanzar**
4. **Commits por fase** con conventional commits
5. **No avanzar a la siguiente fase hasta que la actual esté verificada**