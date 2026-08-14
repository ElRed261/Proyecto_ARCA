# Recomendaciones de Profesionalización — Proyecto ARCA

**Fecha:** Junio 2026  
**Auditores:** Senior Full Stack · Senior Software Architect · Senior Data Architect · Desktop App Specialist  
**Repo:** `ElRed261/Proyecto_ARCA` · **Branch:** `ERP-Meteorológico`  
**Stack real:** Tauri v2.10 + React 19 + Rust (activo) + Python FastAPI (muerto)  
**Alcance:** ~14.200 LOC en 70 archivos

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura: Estado Actual vs. Arquitectura Recomendada](#2-arquitectura-estado-actual-vs-arquitectura-recomendada)
3. [Auditoría Frontend](#3-auditoría-frontend)
4. [Auditoría Backend Rust](#4-auditoría-backend-rust)
5. [Auditoría Backend Python](#5-auditoría-backend-python)
6. [Auditoría Data / Base de Datos](#6-auditoría-data--base-de-datos)
7. [Auditoría de Seguridad Consolidada](#7-auditoría-de-seguridad-consolidada)
8. [Cumplimiento SOLID](#8-cumplimiento-solid)
9. [Escalabilidad](#9-escalabilidad)
10. [Viabilidad, Factibilidad y Sostenibilidad](#10-viabilidad-factibilidad-y-sostenibilidad)
11. [Plan de Remediación por Fases](#11-plan-de-remediación-por-fases)
12. [Conclusión](#12-conclusión)

---

## 1. Resumen Ejecutivo

### Scorecard Global

| Dimensión | Frontend | Backend Rust | Backend Python | Datos/DB | DevOps |
|-----------|----------|--------------|----------------|----------|--------|
| Arquitectura | D | C | F (muerto) | D+ | N/A |
| Seguridad | D | D+ | F | C (sin SQLi) | F |
| SOLID | F (1/5) | F (0/4) | F (0/5) | N/A | N/A |
| Escalabilidad | D | C | F | D | F |
| Testing | F (0%) | F (~5%) | F (0%) | F | F (0/10) |
| Sostenibilidad | D | D | F | D | F (2/10) |

### Veredicto

El proyecto **funciona** como herramienta interna, pero **NO cumple estándares profesionales**. Tiene:

- **8 vulnerabilidades críticas de seguridad** (6 en backend, 2 en DevOps)
- Un backend Python muerto de 1.773 LOC que duplica Rust
- 7 tests sobre 14.200 LOC (cobertura ~1%)
- Cero CI/CD (no existe `.github/workflows/`)
- 7 versiones distintas sin sincronizar (0.1.0 / 2.0.0 / 3.2.0)
- 7 god components que concentran 70% del código frontend
- Cero traits/abstracciones en Rust (SOLID 0/4)
- DB sin migraciones, sin índices, sin foreign keys
- Git hygiene crítica (DB con hashes committed, .gitignore roto)

**La buena noticia:** el módulo `monthly_summary/` demuestra que se sabe hacer arquitectura Hexagonal correcta. El plan es replicar ese patrón al resto del codebase.

---

## 2. Arquitectura: Estado Actual vs. Arquitectura Recomendada

### 2.1 Estado Actual

El proyecto pasó por **3 migraciones arquitectónicas** (Electron -> PySide6 -> Rust/Tauri), y los cadáveres de cada una siguen committed en el repo.

```
Proyecto_ARCA/
├── frontend/                    <- APLICACIÓN ACTIVA
│   ├── src/                     <- React 19 (JS puro, 34 archivos, ~8.500 LOC)
│   │   ├── features/            <- Feature-first (bien sembrado, mal ejecutado)
│   │   │   ├── auth/            <- authService (único con capa de abstracción)
│   │   │   ├── dashboard/       <- OK
│   │   │   ├── synoptic/        <- GOD: SynopticPage.jsx 1270 LOC
│   │   │   ├── summary/         <- GOD: SummaryPage.jsx 1118 LOC
│   │   │   ├── audit/           <- GOD: AuditObservationPage.jsx 924 LOC
│   │   │   └── maintenance/     <- Fantasma (indocumentado)
│   │   └── shared/
│   │       ├── components/      <- 4 piezas sueltas
│   │       ├── api/axiosConfig.js  <- CÓDIGO MUERTO
│   │       └── utils/auth.js    <- Bug de tipos en roles
│   └── src-tauri/               <- Rust backend (22 archivos, ~4.882 LOC)
│       └── src/
│           ├── monthly_summary/ <- HEXAGONAL PARCIAL (template a replicar)
│           ├── audit.rs         <- GOD MODULE 1121 LOC
│           ├── auth.rs          <- Token forgeable
│           ├── db.rs            <- Sin migraciones, sin índices
│           ├── calculations.rs  <- Math + CRUD mezclados
│           └── json_handler/    <- Flat, duplicación masiva
├── backend/                     <- PYTHON MUERTO (1.773 LOC, 740MB .venv)
├── Base para modulos/           <- Submodule roto sin .gitmodules
├── scratch/                     <- Basura committed (__pycache__ incluido)
└── docs/                        <- PDF WMO con copyright + .xlsm con macros
```

### 2.2 Dos Arquitecturas Conviven en Rust

| Módulo | Patrón | Calidad |
|--------|--------|---------|
| `monthly_summary/` | Hexagonal parcial: commands (IPC fina) -> adapters -> domain puro -> pipeline | B+ |
| El resto | Flat / Transaction Script: comandos con lógica + DB + I/O mezclados | D |

`monthly_summary/` es la prueba de que se sabe hacer arquitectura bien. El resto no la usa.

### 2.3 Arquitectura Recomendada: Hexagonal (Ports & Adapters)

**Hexagonal Architecture** adaptada a Tauri. No Clean Architecture completa (over-engineering para desktop single-user). No microservicios. No CQRS.

Ya se tiene la receta funcionando en `monthly_summary/`:

```
monthly_summary/
├── commands.rs      <- IPC fina (solo @tauri::command, delega)
├── calculations.rs  <- Domain puro (sin I/O ni DB)
├── excel_reader.rs  <- Adapter (calamine -> DailyObservation)
├── synop_adapter.rs <- Adapter (JSON -> DailyObservation)
├── json_pipeline.rs <- Orchestration + persistencia
└── config.rs        <- Configuración pura
```

**Plan de expansión al resto del codebase:**

```
src-tauri/src/
├── commands/              <- Capa IPC fina (delega a services)
│   ├── auth_commands.rs
│   ├── audit_commands.rs
│   └── synoptic_commands.rs
├── domain/               <- Lógica pura, sin I/O
│   ├── auth/
│   ├── audit/
│   └── synoptic/
├── ports/               <- Traits (abstracciones)
│   ├── user_repository.rs       (trait UserRepository)
│   ├── observation_repository.rs (trait ObservationRepository)
│   └── audit_repository.rs      (trait AuditRepository)
├── adapters/            <- Implementaciones concretas
│   ├── sqlite_user_repository.rs
│   ├── json_observation_repository.rs
│   └── sqlite_audit_repository.rs
└── infrastructure/      <- DB pool, config, errors, migraciones
    ├── db.rs
    ├── error.rs         (AppError con thiserror)
    ├── migrations/      (refinery o rusqlite_migration)
    └── config.rs
```

**Por qué Hexagonal y no otra:**

- Separación de I/O (crítico: hay SQLite + JSON files como dos data sources)
- Testabilidad del domain sin mocks pesados (calculations.rs ya lo demuestra)
- Comandos Tauri finos que delegan (monthly_summary/commands.rs ya lo hace)
- No agrega complejidad innecesaria para una app local single-user

---

## 3. Auditoría Frontend

### 3.1 Valoración por Dimensión

| Dimensión | Nivel Funcional | Nivel Comodidad | Evidencia |
|-----------|----------------|-----------------|-----------|
| Arquitectura | ALTO - feature-first funciona | MEDIO - sin capa de abstracción | Cero imports cruzados entre features (bien), pero sin container/presentational |
| Componentes | ALTO - 7 god components = 70% del código | CRÍTICO - cambios cuestan 3x | SynopticPage 1270 LOC, SummaryPage 1118 LOC, 6 useEffect en uno |
| State management | ALTO - sessionStorage como store global | CRÍTICO - bug silencioso | `storage` event listener en Cli4074Page:496 es no-op same-tab |
| Type safety | ALTO - JS puro, bug de tipos en roles | ALTO - sin feedback del compilador | `r.toLowerCase()` crashea si `r` es `{name:'admin'}` (DashboardPage:47) |
| Testing | CRÍTICO - 0 tests, 0 framework | CRÍTICO - cada refactor es lotería | Sin vitest, sin jest, sin @testing-library |
| Accesibilidad | ALTO - 0 aria-*, divs como botones | MEDIO - `<html lang="en">` en UI española | 0 resultados de `grep aria-`, modales sin focus trap |
| Seguridad rutas | ALTO - /admin accesible por cualquier logueado | BAJO - ProtectedRoute solo chequea user | App.jsx:18 no valida roles |

### 3.2 Frontend - Hallazgos CRÍTICOS y ALTOS

#### CRÍTICO-F1: 7 God Components concentran 6.000 LOC (70%)

| Archivo | LOC | Responsabilidades mezcladas |
|---------|-----|----------------------------|
| `SynopticPage.jsx` | 1270 | Estado + 6 useEffect + draft sessionStorage + fetch + cálculos + render tabla 16 filas + sidebar |
| `SummaryPage.jsx` | 1118 | Fetch + stats + charts + PDF export + Excel export + history CRUD + sub-componentes definidos inline |
| `Cli4074Page.jsx` | 947 | 24 filas spreadsheet + parser grupos 8 + storage listener (roto) |
| `AuditObservationPage.jsx` | 924 | 2 modales + FIELD_LABELS 80 líneas + render functions |
| `Cli5074Page.jsx` | 682 | Copy-paste de Cli3074/Cli4074 |
| `Cli3074Page.jsx` | 637 | Copy-paste de Cli4074/Cli5074 |
| `AuditReportPage.jsx` | 484 | Borderline |

#### CRÍTICO-F2: Bug de tipos en roles (3 interpretaciones distintas del mismo dato)

```
auth.js:8          -> r.name === 'admin' || r === 'admin'    (object O string)
DashboardPage:47   -> r.toLowerCase()                        (crashea si es object)
SummaryPage:152    -> typeof r === 'string' ? r : r.name     (normaliza)
AdminPage:61       -> roles[0].name                          (asume object)
```

#### CRÍTICO-F3: sessionStorage como store global + listener roto

`Cli4074Page.jsx:496-577` escucha `window.addEventListener('storage')` para sincronizar con SynopticPage. Pero el evento `storage` **no se dispara en la misma pestaña** (solo cross-tab). Es un no-op silencioso.

#### ALTO-F1: 35 comandos invoke() sin capa de abstracción

Cada page invoca `invoke('comando_rust')` directamente. Solo `authService.js` encapsula. Debería replicarse en `synopticService`, `auditService`, `summaryService`.

#### ALTO-F2: Duplicación masiva (DRY violations)

| Duplicación | Archivos | LOC desperdiciadas |
|-------------|----------|-------------------|
| `enforceOneDecimal` definido 3x idéntico | Cli3074, Cli4074, Cli5074 | ~60 |
| `synopRows` mapeo definido 3x | Cli3074, Cli4074, Cli5074 | ~90 |
| `FIELD_LABELS` duplicado | AuditObservationPage, AuditReportPage | ~160 |
| Estado inicial 24 filas repetido 3x en mismo archivo | Cli4074Page | ~120 |
| Scrollbar CSS via dangerouslySetInnerHTML | Cli3074, Cli4074 | ~20 |

#### ALTO-F3: Dead code - axios + axiosConfig.js

`axiosConfig.js` apunta a `http://127.0.0.1:8000/api` (FastAPI muerto). Nadie lo importa. `axios` (27KB gzip) está en el bundle sin razón.

#### ALTO-F4: Race conditions en async Tauri invoke

- `SynopticPage.jsx:545` - `handleHourChange` dispara `doQuietSave()` + `setActiveHour()` pero `performCalculations` está debounced 300ms con closure stale
- `AuditObservationPage.jsx:169` - `loadObservation` usa `activeHour` del closure del effect `[station, date]` - stale closure
- Sin AbortController ni flag in-flight en ningún lado

#### ALTO-F5: JSON.parse sin try/catch en 5 lugares

`App.jsx:40`, `AuditObservationPage.jsx:144`, `SummaryPage.jsx:151`, `SynopticPage.jsx:303-305,523-525,572`. Si el storage se corrompe, la app crashea.

### 3.3 Frontend - Lo Positivo

- Feature isolation: cero imports cruzados entre features (verificado)
- `ModuleCard.jsx` - props-driven, extensible (ejemplo a seguir)
- `authService.js` - única capa de abstracción correcta
- Controlled inputs en todos los forms
- Sin TODO/FIXME/HACK comments (limpio)
- `react-hot-toast` accesible por defecto

---

## 4. Auditoría Backend Rust

### 4.1 Valoración por Dimensión

| Dimensión | Nivel Funcional | Nivel Comodidad | Evidencia |
|-----------|----------------|-----------------|-----------|
| Arquitectura | MEDIO - funciona, monthly_summary es B+ | ALTO - audit.rs 1121 LOC imposible de mantener | 2 arquitecturas conviven |
| Seguridad | CRÍTICO - 6 findings críticos | ALTO - sin tipo de error, errores filtran paths | Token forgeable, path traversal x2 |
| SOLID | CRÍTICO - 0/4 aplicables | ALTO - cero traits, cero abstracciones | Sin interfaces, todo concreto |
| Testing | CRÍTICO - 7 tests en 1 archivo | CRÍTICO - audit.rs 1121 LOC sin tests | ~5% coverage |
| DB | ALTO - sin migraciones, sin índices | MEDIO - pool subutilizado | 50% de comandos bypassa el pool |
| Code quality | MEDIO - funciona | ALTO - Stringly-typed errors, 31 unwraps | Sin thiserror, duplicación masiva |

### 4.2 Backend Rust - Hallazgos CRÍTICOS

#### CRÍTICO-B1: Credenciales admin hardcodeadas - `db.rs:135-139`

```rust
("admin@arca.rd", "admin123", "admin"),
("encargado@arca.rd", "encargado123", "encargado"),
("observador@arca.rd", "observador123", "observador"),
("calidad@arca.rd", "calidad123", "control_calidad"),
```

Se re-insertan en cada boot si faltan (líneas 150-167). No se pueden borrar definitivamente. Cualquiera con acceso al repo conoce las creds admin.

#### CRÍTICO-B2: Token de sesión forgeable - `auth.rs:63-65,174`

```rust
let token_payload = format!("{}:{}:{}", id, role, chrono::Utc::now().timestamp());
let access_token = b64_encode(&token_payload);  // b64_encode hace HEX, no base64
```

No está firmado (sin HMAC/secret). No tiene expiración validada. No se valida en ningún comando posterior. La "autenticación" es teatro.

#### CRÍTICO-B3: Autorización server-side inexistente

`validate_user_role` (auth.rs:184) está definida pero **nunca llamada**. El comentario en `audit.rs:644-645` lo admite:

```rust
// Como solo el admin o control_calidad pueden invocar esto (validado en frontend),
// se aprueba directamente al guardarse
```

Desde IPC de Tauri, cualquier webview puede invocar `delete_user`, `change_password`, `audit_propose_correction` sin chequeo de rol.

#### CRÍTICO-B4: Path traversal - borrado arbitrario de archivos - `monthly_summary/commands.rs:178`

```rust
pub async fn ms_delete_summary(path: String) -> Result<(), String> {
    trash::delete(Path::new(&path))  // borra CUALQUIER archivo del sistema
}
```

Cero validación. `ms_export_excel` sobreescribe cualquier path.

#### CRÍTICO-B5: Path traversal en audit_export_corrected_json - `audit.rs:807-826`

`station_id` no se valida. Con `station_id = "../../etc"` se escapa del base dir y se escribe JSON en cualquier lado.

#### CRÍTICO-B6: Spoofing de identidad - `audit.rs:540,633`

`marcado_por`, `corregido_por`, `aprobado_por` llegan como `String` desde el frontend y se persisten verbatim. Sin binding al usuario autenticado. Un observador puede marcar errores "como" el admin.

### 4.3 Backend Rust - Hallazgos ALTOS

#### ALTO-B1: audit.rs God Module (1121 LOC, 11 comandos)

Mezcla IPC + DB + filesystem + JSON + cálculos metereológicos. `audit_load_observation` (líneas 328-529) hace 5 responsabilidades distintas.

#### ALTO-B2: 31 unwrap() - riesgo de panic en producción

Los peores: `json_pipeline.rs:278-304` (21 unwraps en export Excel), `synop_adapter.rs:19,35` (`chars().next().unwrap()` con bug latente UTF-8 - `.len()` cuenta bytes no chars).

#### ALTO-B3: Errores Stringly-typed - 45 comandos con Result<T, String>

Sin `thiserror`, sin `enum AppError`. `.map_err(|e| e.to_string())?` repetido ~40 veces. El frontend no puede distinguir "no encontrado" de "error interno". Errores filtran paths internals (audit.rs:829).

#### ALTO-B4: Duplicación masiva

| Duplicación | Archivos | LOC desperdiciadas |
|-------------|----------|-------------------|
| save_cli3074/4074/5074_json idénticos salvo key | cli.rs | ~150 |
| Tabla visibilidad duplicada | cli_autofill.rs + synoptic.rs | ~75 |
| `calc_car` duplica `calcular_tendencia_a` | synoptic.rs + calculations.rs | ~40 |
| Build de filtros WHERE LIKE duplicado | audit.rs:696-746 + 1005-1095 | ~140 |
| Mapeo SYNOP ida/vuelta desincronizado | synoptic.rs:8-58 vs 71-100 | ~60 |

#### ALTO-B5: Sin migraciones, sin índices, sin FKs

- `CREATE TABLE IF NOT EXISTS` no actualiza esquemas existentes
- Cero `CREATE INDEX` - `error_marks` y `corrections` filtrados por `(station_id, fecha)` son full scan
- `PRAGMA foreign_keys=ON` nunca se setea
- Tablas muertas: `audit_logs`, `correction_requests` (creadas, jamás usadas)
- Dependencia zombi: `lazy_static` (Cargo.toml:26) - no se usa en ningún `src/`

#### ALTO-B6: App sigue viva si init_db falla - `lib.rs:66-73`

Si `init_db` falla, los comandos que piden `State<DbPool>` paniquearán al invocarse, pero la app sigue corriendo en estado roto. Debería ser fatal.

#### ALTO-B7: N+1 Query en audit_browse_days - `audit.rs:216-322`

Por cada archivo JSON del mes, ejecuta 2 `COUNT(*)` sin índices. 31 días -> 62 full scans.

### 4.4 Backend Rust - Lo Positivo

- Queries SQL **parametrizadas** en todo el codebase - **no hay SQL injection**
- `validate_inputs` (utils.rs:89) sanitiza `station_code` (alphanumeric+`_`, max 10) y `fecha` (dígitos)
- bcrypt con `DEFAULT_COST` para passwords
- WAL mode (db.rs:28) - bien para concurrencia de lectura
- `monthly_summary/` - hexagonal parcial, domain puro sin I/O, adapter pattern
- Capabilities minimal sin wildcards (capabilities/default.json)
- 7 tests unitarios en calculations.rs (Magnus-Tetens, SYNOP)
- Soft-delete en `delete_user` (preserva integridad)
- Pool r2d2 creado (aunque subutilizado)

---

## 5. Auditoría Backend Python

### 5.1 Veredicto: 100% LEGACY, MUERTO, SIN CONSUMIDORES

| Evidencia | Fuente |
|-----------|--------|
| `run_full.sh` no arranca uvicorn | línea 38: solo `npm run tauri:dev` |
| Frontend no lo llama | 54 `invoke()` a Rust, 0 HTTP a Python |
| `axiosConfig.js` es código muerto | grep: ningún archivo lo importa |
| README v3.2.0 declara "Backend Rust" | no menciona Python |
| 0 commits desde 2026-01-30 | git log confirma |
| Datos stale de dic 2025 | `backend/app/modules/synoptic/data/` |
| 740MB `.venv` muerto | `backend/.venv/` |
| `psycopg2-binary` para Postgres abandonado | Oracle Cloud plan descartado |

### 5.2 Python - Hallazgos de Seguridad (si se conservara)

| # | Severidad | Hallazgo | Archivo:línea |
|---|-----------|----------|---------------|
| SEC-01 | CRÍTICO | `SECRET_KEY` default hardcodeado `"ARCA_LOCAL_SECRET_KEY_2025"` | `core/config.py:21` |
| SEC-02 | CRÍTICO | Credenciales impresas en claro a stdout | `init_db.py:88-93` |
| SEC-03 | ALTO | Path traversal sin sanitizar `station_code` | `json_handler.py:29-33,298` |
| SEC-04 | ALTO | Sin autorización por rol fuera de admin | `synoptic/router.py`, `audit/router.py` |
| SEC-07 | MEDIO | Inputs numéricos como `Optional[str]` (Pydantic desaprovechado) | `synoptic/schemas.py:26-43` |

### 5.3 Duplicación Rust vs Python

| Concepto | Python | Rust | Divergencia |
|----------|--------|------|-------------|
| Cálculos meteo | `calculations.py` (476 LOC) | `calculations.rs` (417 LOC) | Idénticos algoritmos, 2 lenguajes |
| JSON handler | `json_handler.py` (417 LOC) | `synoptic.rs` + `utils.rs` | Misma lógica |
| Auth | `security.py` (JWT firmado) | `auth.rs` (hex forgeable) | **Rust es regresión de seguridad** |
| Seed estaciones | `calculations.py:13-29` (dict) | `db.rs:186-202` (tabla) | Rust mejoró |
| Seed usuarios | `init_db.py:50-66` | `db.rs:134-139` | Mismas creds |
| Esquema DB | SQLAlchemy (users, roles, user_roles M2M) | rusqlite (users con role TEXT) | Incompatibles |

### 5.4 Recomendación: Eliminar el Backend Python

El Rust tiene **MÁS funcionalidad** que el Python (CLI 3074/4074/5074, export Excel, autofill, app_config - todo ausente en Python). No hay un solo consumidor vivo del backend Python. El costo de mantenerlo es 100% overhead.

**Acción:** `git rm -r backend/` + `git rm frontend/src/shared/api/axiosConfig.js` + eliminar `axios` de `package.json`.

---

## 6. Auditoría Data / Base de Datos

### 6.1 Esquema Actual (Rust, 8 tablas)

```
users              (id, email, password_hash, role TEXT, active, created_at)
audit_logs         <- MUERTA (creada, jamás usada)
summary_logs       (id, station_id, year, month, data TEXT)
correction_requests <- MUERTA (creada, jamás usada)
error_marks        (id, station_id, fecha, field, marked_by, marked_at, note)
corrections        (id, station_id, fecha, field, original_value, corrected_value,
                    corrected_by, corrected_at, status, updated_at <- nunca updated)
app_config         (key, value)
stations           (id, code, name, latitude, longitude, elevation, assigned_to)
```

### 6.2 Valoración

| Dimensión | Nivel | Evidencia |
|-----------|-------|-----------|
| Integridad referencial | CRÍTICO | Sin FKs, `PRAGMA foreign_keys` nunca ON, borrar estación deja huérfanos |
| Migraciones | CRÍTICO | No existe sistema. `CREATE TABLE IF NOT EXISTS` no evoluciona esquema |
| Índices | ALTO | Cero índices. `error_marks`/`corrections` filtrados por `(station_id, fecha)` = full scan |
| Connection pool | MEDIO | r2d2 creado pero 50% de comandos abre `Connection::open` fresco |
| SQL injection | ÓPTIMO | Todas las queries parametrizadas con `?` + `params![]` |
| Esquema limpio | ALTO | 2 tablas muertas, `corrections.updated_at` nunca se actualiza |
| Concurrencia | BAJO | WAL mode activo (bien para single-user) |

### 6.3 Recomendaciones Data

1. **Sistema de migraciones**: `refinery` o `rusqlite_migration` con `PRAGMA user_version`
2. **Índices**: `CREATE INDEX idx_error_marks_station_fecha ON error_marks(station_id, fecha)` + análogo para `corrections` + `summary_logs(station_id, year, month)`
3. **Foreign keys**: `PRAGMA foreign_keys=ON` tras abrir pool + `station_id REFERENCES stations(id)`
4. **Limpieza**: borrar tablas muertas `audit_logs` y `correction_requests`
5. **Pool consistente**: todos los comandos deben usar `State<DbPool>`, no `Connection::open` fresco
6. **Fix N+1**: `audit_browse_days` - reemplazar 2 COUNT(*) por archivo por un solo `GROUP BY fecha` + join in-memory

---

## 7. Auditoría de Seguridad Consolidada

### 7.1 Findings por Severidad

| # | Severidad | Área | Hallazgo | Archivo |
|---|-----------|------|----------|---------|
| C-1 | CRÍTICO | Backend | Credenciales admin hardcodeadas | `db.rs:135-139` |
| C-2 | CRÍTICO | Backend | Token forgeable (hex sin HMAC) | `auth.rs:63-65` |
| C-3 | CRÍTICO | Backend | Autorización server-side inexistente | `auth.rs:184` (muerto) |
| C-4 | CRÍTICO | Backend | Spoofing de identidad en audit | `audit.rs:540,633` |
| C-5 | CRÍTICO | Backend | Path traversal - borrado arbitrario | `monthly_summary/commands.rs:178` |
| C-6 | CRÍTICO | Backend | Path traversal - escritura arbitraria | `audit.rs:807-826` |
| C-7 | CRÍTICO | DevOps | DB con hashes bcrypt committed al repo | `backend/arca_local.db` |
| C-8 | CRÍTICO | DevOps | Credenciales en run_full.sh | `run_full.sh:60-63` |
| H-1 | ALTO | Frontend | /admin accesible sin chequeo de rol | `App.jsx:18` |
| H-2 | ALTO | Backend | Enumeración de usuarios por timing oracle | `auth.rs:38-61` |
| H-3 | ALTO | Backend | App sigue viva si init_db falla | `lib.rs:66-73` |
| H-4 | ALTO | Backend | 31 unwrap() - panic en producción | `json_pipeline.rs:278-304` |
| H-5 | ALTO | Backend | shell.open: true habilitado | `tauri.conf.json:45` |
| H-6 | ALTO | Deps | xlsx 0.18.5 con CVEs conocidos | `package.json:29` |
| M-1 | MEDIO | Backend | CSP permite style-src 'unsafe-inline' | `tauri.conf.json:25` |
| M-2 | MEDIO | Backend | Errores filtran paths internals al frontend | `audit.rs:829` |
| M-3 | MEDIO | Backend | tauri compilado con feature test en producción | `Cargo.toml:24` |
| M-4 | MEDIO | Frontend | localStorage para token (debería ir a keyring OS) | `authService.js:9` |

### 7.2 Lo Positivo de Seguridad

- Queries SQL parametrizadas en todo el codebase - **cero SQL injection**
- `validate_inputs` sanitiza `station_code` y `fecha` en `json_handler/*`
- bcrypt con `DEFAULT_COST`
- Capabilities minimal sin wildcards (capabilities/default.json)
- WAL mode para concurrencia

---

## 8. Cumplimiento SOLID

### 8.1 Backend Rust

| Principio | Veredicto | Evidencia |
|-----------|-----------|-----------|
| **S** Single Responsibility | FAIL | `audit.rs` (1121 LOC) mezcla IPC + DB + fs + JSON + cálculos. `calculations.rs` mezcla math pura con 5 comandos CRUD. `db.rs` mezcla esquema + pool + seed. |
| **O** Open/Closed | FAIL | Cero traits. Agregar un campo meteo nuevo requiere editar `match` en 4 lugares distintos. Todo modificación, nada extensión. |
| **L** Liskov | N/A | No hay jerarquías de traits. Cero traits definidos. |
| **I** Interface Segregation | FAIL | Sin traits, los "contratos" son structs concretos. Comandos aceptan `serde_json::Value` sin tipo. |
| **D** Dependency Inversion | FAIL | Comandos dependen de `Connection` concreto, `DbPool` concreto, `get_db_path` concreto. |

**Score: 0/4 aplicables.** Excepción: `monthly_summary/calculations.rs` es domain puro sin I/O.

### 8.2 Frontend React

| Principio | Veredicto | Evidencia |
|-----------|-----------|-----------|
| **S** Single Responsibility | FAIL | SynopticPage: 6 responsabilidades en 1 archivo. SummaryPage define sub-componentes inline (se re-montan cada render). |
| **O** Open/Closed | PARTIAL FAIL | CLI pages son copy-paste. Para agregar CLI 6074 hay que modificar los 3 existentes + App.jsx. `ModuleCard.jsx` es el único extensible. |
| **L** Liskov | N/A | Sin herencia, composition only (bien). |
| **I** Interface Segregation | PARTIAL | `StationHeader.jsx` interfaz limpia (7 props). `SynopticSidebar.jsx` 11 props (pero no se usa). `AuthPage.jsx` `addLog` es wrapper de console.log. |
| **D** Dependency Inversion | FAIL | Cada page invoca `invoke('comando')` directamente. Sin capa de abstracción excepto `authService`. Dependencia fuerte en `localStorage`/`sessionStorage` concreto. |

**Score: 1 parcial / 4 aplicables.**

### 8.3 Backend Python (si se conservara)

| S | O | L | I | D |
|---|---|---|---|---|
| PARCIAL | FAIL | N/A | FAIL | FAIL |

`STATIONS` dict hardcodeado. Cero Protocol/ABC. `engine`/`SessionLocal` globales. `Base.metadata.create_all` como side-effect de import.

---

## 9. Escalabilidad

### 9.1 Qué Escala

| Componente | Veredicto | Razón |
|------------|-----------|-------|
| `monthly_summary/calculations.rs` | ÓPTIMO | Domain puro, testeable, paralelizable |
| Pool r2d2 (cuando se usa) | BAJO | Maneja concurrencia OK para desktop |
| WAL mode | BAJO | Readers concurrentes sin bloquear |
| Feature isolation frontend | MEDIO | Cero imports cruzados, escala en módulos |

### 9.2 Qué NO Escala

| Bottleneck | Nivel | Impacto |
|------------|-------|---------|
| `audit.rs` monolítico 1121 LOC | CRÍTICO | No escala en equipo. Cualquier cambio choca con otro. |
| Sin migraciones | CRÍTICO | No escala en tiempo de producto. Cada cambio de esquema es risk manual. |
| 7 god components frontend | ALTO | No escala en equipo. Resistencia al onboarding. |
| N+1 en `audit_browse_days` | ALTO | 62 full scans por mes sin índices |
| `walkdir` full recursión sin paginación | ALTO | Con años de historia, degrada linealmente |
| Sin tests (7/14.200 LOC) | CRÍTICO | No escala en confianza. Cada refactor es lotería. |
| Pool subutilizado | MEDIO | Conexiones frescas por comando derrochan el pool |
| `serde_json::Value` sin tipo | MEDIO | Parseo reiterado sin struct fuerte, schema drift silencioso |
| sessionStorage como store | ALTO | No reactivo, propenso a colisiones, bug same-tab |

### 9.3 Límite Realista

Es una **desktop app local single-user**. El volumen (una estación, datos diarios) es chico. Los bottlenecks de performance no son agudos hoy. Pero el bottleneck de **mantenibilidad** ya está cobrando cara: cualquier feature nueva cuesta más de lo que debería porque hay que navegar 1121 LOC en audit.rs o 1270 en SynopticPage sin tests que respalden.

---

## 10. Viabilidad, Factibilidad y Sostenibilidad

### 10.1 Viabilidad Técnica

| Aspecto | Nivel | Observación |
|---------|-------|-------------|
| Stack elegido (Tauri+Rust+React) | ÓPTIMO | Correcto para desktop app local con cálculos numéricos |
| Funcionalidad core implementada | ALTO | Synoptic, CLI, audit, summary, auth - todo funciona |
| Rendimiento desktop | BAJO | Adecuado para single-user local |
| Backend dual (Python+Rust) | CRÍTICO | Insostenible, Python no tiene consumidores |
| Migración Electron->Tauri | ÓPTIMO | Decisión correcta, pero cadáveres sin limpiar |

### 10.2 Factibilidad de Profesionalización

| Aspecto | Nivel | Esfuerzo Estimado |
|---------|-------|-------------------|
| Fix de seguridad crítico (auth + path traversal) | Alcanzable | 3-5 días |
| Refactor audit.rs a hexagonal | Alcanzable | 1 semana (template en monthly_summary) |
| Migración JS -> TypeScript | Alcanzable | 1-2 sprints |
| Romper god components frontend | Alcanzable | 1-2 sprints |
| Sistema de migraciones DB | Alcanzable | 2-3 días (refinery) |
| CI/CD desde cero | Alcanzable | 1 día (1 workflow file) |
| Testing desde cero | Alcanzable | Incremental, empezar por utils puras |
| Eliminar Python muerto | Alcanzable | 1 hora (git rm + cleanup) |

### 10.3 Sostenibilidad

| Aspecto | Nivel | Evidencia |
|---------|-------|-----------|
| Bus factor | CRÍTICO (1) | Autor único, sin CONTRIBUTING |
| LICENSE | CRÍTICO | No existe. Legalmente no se puede distribuir |
| ADRs | CRÍTICO | No hay. Nadie sabe por qué Electron->PySide6->Rust |
| Versiones | ALTO | 7 versiones distintas (0.1.0 / 2.0.0 / 3.2.0) |
| Reproducibilidad entorno | ALTO | Sin rust-toolchain.toml, sin .nvmrc |
| Doc vs código | ALTO | README describe arquitectura aspiracional, no real |
| Git hygiene | CRÍTICO | DB, logs, .bak, datos reales committed; .gitignore roto línea 18 |
| Submodule roto | ALTO | `Base para modulos/Resumen_Mensual_Synop` sin .gitmodules |

**Sustainability score: 2/10**

---

## 11. Plan de Remediación por Fases

### Fase 0 - Remediación de Seguridad INMEDIATA (3-5 días)

| # | Acción | Archivo | Prioridad |
|---|--------|---------|-----------|
| 0.1 | Reemplazar token hex por HMAC-SHA256 con secret de config, O usar sesión in-memory (la app es local) | `auth.rs:63-65` | CRÍTICA |
| 0.2 | Llamar `validate_user_role` en comandos sensibles (delete_user, change_password, audit_propose_correction) | `auth.rs:184` | CRÍTICA |
| 0.3 | Validar paths en `ms_load_summary`/`ms_export_excel`/`ms_delete_summary` - canonicalizar y verificar que está dentro de `get_monthly_summary_dir()` | `monthly_summary/commands.rs` | CRÍTICA |
| 0.4 | Validar `station_id` con `validate_inputs` en `audit_export_corrected_json` | `audit.rs:807` | CRÍTICA |
| 0.5 | Sacar credenciales del código. Sembrar random en first-run + forzar cambio de password | `db.rs:135-139` | CRÍTICA |
| 0.6 | Binding de `marcado_por`/`corregido_por` al usuario autenticado server-side | `audit.rs:540,633` | CRÍTICA |
| 0.7 | `ProtectedRoute` con roles: crear `<RoleRoute roles={['admin']}>` para `/admin` y `/audit` | `App.jsx:18` | ALTA |
| 0.8 | `git rm --cached backend/arca_local.db` + purgar historial con `git filter-repo` | repo | CRÍTICA |
| 0.9 | Sacar credenciales de `run_full.sh:60-63` | `run_full.sh` | CRÍTICA |

### Fase 1 - Detener la Hemorragia (1 semana)

| # | Acción | Impacto |
|---|--------|---------|
| 1.1 | **Eliminar backend Python**: `git rm -r backend/` + `git rm frontend/src/shared/api/axiosConfig.js` + eliminar `axios` de package.json | -1773 LOC, -740MB, -29 deps |
| 1.2 | **Arreglar `.gitignore`** línea 18 (split `*.swp` y `Base para modulos/`). Agregar: `*.log`, `*.db`, `*.bak`, `__pycache__/`, `.venv/`, `*.xlsm` | Git hygiene |
| 1.3 | **`git rm --cached`** de: `backend.log`, `frontend.log`, `scratch/__pycache__/`, `docs/*.pdf`, `docs/*.xlsm` | Datos sensibles fuera |
| 1.4 | **CI mínima**: crear `.github/workflows/ci.yml` con `cargo test`, `cargo clippy -- -D warnings`, `npm run lint`, `npm run build` | 0 -> CI básica |
| 1.5 | **Sincronizar versiones**: un source of truth en `tauri.conf.json`, script que actualice `package.json`, `Cargo.toml`, `README` | 7 -> 1 versión |
| 1.6 | **Agregar `LICENSE`** (MIT o Apache-2.0) | Legal |
| 1.7 | **Eliminar submodule roto** o arreglar con `.gitmodules` | Estructura |
| 1.8 | **Mover `scratch/`** fuera del repo | Limpieza |
| 1.9 | **`rust-toolchain.toml` + `.nvmrc`** | Reproducibilidad |
| 1.10 | **Eliminar `lazy_static`** de Cargo.toml (zombi) y `tauri` feature `test` para release | Limpieza deps |

### Fase 2 - Arquitectura (2-3 sprints)

| # | Acción | Template |
|---|--------|----------|
| 2.1 | **Crear `infrastructure/error.rs`** con `enum AppError` (thiserror). Reemplazar `Result<T, String>` en los 45 comandos | - |
| 2.2 | **Refactor `audit.rs`** -> split en `audit/commands.rs` (IPC fina), `audit/repository.rs` (queries), `audit/service.rs` (lógica overlay), `audit/export.rs` | `monthly_summary/` |
| 2.3 | **Definir traits** `UserRepository`, `ObservationRepository`, `AuditRepository` en `ports/` | - |
| 2.4 | **Migraciones**: agregar `refinery`, mover `CREATE TABLE` a `migrations/0001_init.sql`, `0002_add_indexes.sql` | - |
| 2.5 | **Índices**: `error_marks(station_id, fecha)`, `corrections(station_id, fecha)`, `summary_logs(station_id, year, month)` | - |
| 2.6 | **`PRAGMA foreign_keys=ON`** + FKs `station_id REFERENCES stations(id)` | - |
| 2.7 | **Borrar tablas muertas** `audit_logs` y `correction_requests` | - |
| 2.8 | **Pool consistente**: todos los comandos usan `State<DbPool>` | - |
| 2.9 | **De-duplicar CLI**: colapsar 3 `save_cli*`/`load_cli*` en `save_cli_json(key)` + `load_cli_json(key)` | ~150 LOC -> ~50 |
| 2.10 | **Unificar tabla visibilidad**: una sola `const VIS_TABLE` compartida | - |
| 2.11 | **Mapeo SYNOP**: generar `to_frontend_name` desde `FRONTEND_TO_SYNOP` automáticamente (BiMap o macro) | - |

### Fase 3 - Frontend Profesional (2-3 sprints)

| # | Acción | Impacto |
|---|--------|---------|
| 3.1 | **Migrar a TypeScript** con `strict: true`. Renombrar `.jsx` -> `.tsx` | Elimina clase entera de bugs |
| 3.2 | **Definir tipos compartidos** Rust<->Frontend (replicar serde structs como `types/*.ts`) | Contrato 1:1 |
| 3.3 | **Agregar Zod** para validar respuestas de `invoke()` en el boundary | Runtime safety |
| 3.4 | **Romper god components**: extraer `useSynopticObservation()` hook, `synopticService.js`, componentes `<MeteoRow>`, `<CalcRow>`, `<HourSidebar>` | Meta: ningún page > 250 LOC |
| 3.5 | **Zustand** para estado global: `useAuthStore`, `useStationStore`, `useDraftStore` (persistido a sessionStorage via middleware) | Reemplaza props drilling + sessionStorage store |
| 3.6 | **Capa de servicios**: `synopticService`, `auditService`, `summaryService` (replicar `authService`) | Dependency inversion |
| 3.7 | **Fix bug roles**: centralizar en `useAuthStore.hasRole('admin')` que maneje string\|object una sola vez | Elimina bug latente |
| 3.8 | **Accesibilidad**: `<html lang="es">`, `aria-label` en botones icono, `<div onClick>` -> `<button>`, `role="dialog"` + Escape en modales, `htmlFor`/`id` en labels | a11y mínimo |
| 3.9 | **Eliminar dead code**: `axiosConfig.js`, `SynopticSidebar.jsx` (no usado), `axios` dep | -27KB bundle |

### Fase 4 - Testing y Calidad (incremental, continuo)

| # | Acción | Meta |
|---|--------|------|
| 4.1 | **Rust**: tests para `auth.rs` (login success/fail, bcrypt), `db.rs` (init, pool), `json_handler/synoptic.rs` (save/load round-trip), `audit.rs` (overlay correcciones). Usar `tempfile` para SQLite in-memory | >40% coverage módulos críticos |
| 4.2 | **Frontend**: instalar Vitest + @testing-library/react. Empezar por `synopticUtils.js` (pure) y `authService` (mock invoke) | 20% smoke tests |
| 4.3 | **ESLint estricto**: agregar `eslint-plugin-jsx-a11y` + `eslint-plugin-import` con `import/no-cycle` | Prevenir bugs futuros |
| 4.4 | **CI gate**: `lint && typecheck && test` antes de merge | Prevenir regresiones |
| 4.5 | **Dependabot** + `cargo audit` en CI | Security scan automático |
| 4.6 | **Sacar `xlsx` 0.18.5** (CVEs) - migrar a `rust_xlsxwriter` solo en Rust, o actualizar SheetJS desde su CDN | Elimina CVEs |

### Fase 5 - Tipado de Comentarios y Documentación (continuo)

| # | Acción | Estándar |
|---|--------|----------|
| 5.1 | **Rust doc comments `///`** en todos los comandos públicos y funciones de dominio. `cargo doc --open` debe ser útil para onboarding | rustdoc |
| 5.2 | **JSDoc/TSDoc** en todos los servicios y hooks del frontend | TSDoc |
| 5.3 | **Typos en código**: `nuvocidad` -> `nubosidad` (json_pipeline.rs:84,86,88,272-273), `MAxima` -> `Máxima` (json_pipeline.rs:62), `b64_encode` -> `hex_encode` (auth.rs:174) | Naming correcto |
| 5.4 | **Idioma consistente**: decidir ES o EN para nombres de funciones y mantenerlo. Hoy: `realizar_calculos` (es) vs `calc_dif` (en) | Convención única |
| 5.5 | **CONTRIBUTING.md** con convención de commits (ya usan conventional commits, formalizarlo), política de branches | Governance |
| 5.6 | **CHANGELOG.md** (keep-a-changelog format) | Governance |
| 5.7 | **ADR-001**: documentar decisión Electron->PySide6->Rust/Tauri | Contexto para futuros maintainers |
| 5.8 | **ADR-002**: documentar decisión de eliminar backend Python | Contexto |
| 5.9 | **Actualizar README** para reflejar arquitectura real (no aspiracional) | Doc honesta |

### Cronograma Sugerido

```
Semana 1     -> Fase 0 (seguridad crítica) + Fase 1 (hemorragia git/CI)
Semana 2-3   -> Fase 2.1-2.4 (error types + audit.rs refactor + migraciones + índices)
Semana 4-5   -> Fase 3.1-3.5 (TypeScript + romper god components + Zustand)
Semana 6     -> Fase 2.9-2.11 (de-duplicación Rust) + Fase 3.6-3.9 (servicios + a11y)
Semana 7+    -> Fase 4 (testing incremental) + Fase 5 (docs y comentarios)
```

---

## 12. Conclusión

El proyecto **funciona** como herramienta interna. No es un desastre total. Pero está construido sobre arena:

- **6 vulnerabilidades CRÍTICAS de seguridad** que permiten desde suplantar admin hasta borrar archivos arbitrarios del sistema
- Un **backend Python muerto** de 1.773 LOC que duplica Rust y pesa 740MB
- **7 tests sobre 14.200 LOC** - esencialmente sin testing
- **Cero CI/CD** - cualquier commit roto llega a main
- **7 god components** que concentran 70% del código y son imposibles de mantener
- **Cero traits/abstracciones** en Rust - SOLID 0/4
- **DB sin migraciones, sin índices, sin FKs**
- **Git hygiene CRÍTICA** - DB con hashes committed, .gitignore roto

**La buena noticia:** se tiene el template de arquitectura correcta en `monthly_summary/`. Se sabe hacer Hexagonal. El plan es replicar ese patrón al resto. Y se tiene convención de commits ya establecida.

**La prioridad #1 es seguridad.** Después, parar la hemorragia git. Después, arquitectura. El resto es deuda técnica que se paga con refactor incremental.

---

*Documento generado a partir de auditoría técnica completa con análisis de 4 áreas en paralelo: Backend Rust/Tauri, Frontend React, Backend Python, y DevOps/Testing/CI-CD.*
