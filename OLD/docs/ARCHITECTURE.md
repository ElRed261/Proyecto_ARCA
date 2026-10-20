# Arquitectura Monolito Modular — Proyecto ARCA

> Estado: **esqueleto en rama `refactor/modular-monolith`**. El código actual
> NO se ha movido todavía: esta estructura es el mapa objetivo y la guía de
> migración incremental. La build actual queda intacta.

---

## 1. Principio rector

Cada módulo es una **unidad de dominio independiente**: se desarrolla, se
testea y se modifica por su cuenta. Los módulos se conectan **en secuencia
por datos**, nunca por código: un módulo consume el output que otro produce
(a través de los contratos en `domain/models.rs` y de los archivos de día en
disco). El acoplamiento entre módulos es **cero imports cruzados**.

```
secuencia de datos:
  auth ──(quién puede)──> synoptic ──(día JSON)──> cli ──(cli embedido)──┐
                                                            └─────────────┼──> monthly_summary ──(KPIs)──> UI/export
                                                            └─────────────┼──> audit ──(marks/corrections)──> reportes
```

- `auth` habilita el uso (sesión/roles).
- `synoptic` produce el día de observación (`DayRecord`).
- `cli` enriquece el mismo día (hojas 3074/4074/5074 embebidas).
- `monthly_summary` consume días → KPIs mensuales → Excel/gráficos.
- `audit` consume días + marcas/correcciones en DB → revisión y reportes.

Un cambio en `synoptic` puede cambiar el *contenido* de lo que `monthly_summary`
consume, pero **no puede romper su estructura**: el contrato (`DayRecord` +
`schema_version`) es lo único que ambos ven.

---

## 2. Estructura objetivo (`frontend/src-tauri/src/`)

```
src/
├── lib.rs                  # COMPOSITION ROOT: plugins, estado gestionado, registro de comandos
├── main.rs
│
├── app/                    # CAPA DE APLICACIÓN: comandos Tauri FINOS + orquestación entre módulos
│   └── mod.rs              # (nuevo — esqueleto)
│
├── domain/                 # CONOCIMIENTO COMPARTIDO PURO — cero dependencias internas
│   ├── mod.rs
│   ├── errors.rs           # AppError (único tipo de error del crate)   [migrar de infrastructure/error.rs]
│   ├── models.rs           # Contratos entre módulos: DayRecord, HourObservation, CliRecord, MonthlyKpis,
│   │                       #   AuditMark, Correction  (hoy definidos implícitamente en JSON sin versionar)
│   └── wmo/                # Fuente ÚNICA de tablas WMO y grupos SYNOP (hoy duplicadas ×3)
│
├── modules/                # MÓDULOS DE DOMINIO — independientes, sin imports entre sí
│   ├── mod.rs
│   ├── synoptic/           # Día de observación: lógica de formulario + cálculos + día JSON (PRODUCE DayRecord)
│   │                       #   [migrar de json_handler/synoptic.rs + calculations.rs]
│   ├── cli/                # Hojas CLI 3074/4074/5074: autofill + persistencia (CONSUME DayRecord)
│   │                       #   [migrar de json_handler/cli.rs; DESCARTAR cli_autofill.rs — muerto]
│   ├── auth/               # Usuarios, sesiones, roles (no consume datos de dominio)
│   │                       #   [migrar de auth.rs]
│   ├── monthly_summary/    # YA ESTABLECIDO — módulo aislado de referencia. Se queda donde está.
│   └── audit/              # YA ESTABLECIDO — revisión de días + marks/correcciones. Se queda donde está.
│
├── infrastructure/         # DETALLES TÉCNICOS — db, pool, paths, backups, escritura atómica
│   ├── mod.rs
│   ├── error.rs            # (se vacía al migrar AppError a domain/errors.rs)
│   ├── db.rs               # pool r2d2 + migraciones rusqlite_migration  [se queda]
│   ├── storage/            # convención de paths ARCA + backups + temp+rename  [extraer de json_handler/utils.rs]
│   ├── adapters/           # SqliteUserRepository, SqliteAuditRepository  [se quedan]
│   └── repositories/       # StationsRepository  [se queda]
│
└── ports/                  # CONTRATOS DE PERSISTENCIA  [se quedan — corregir dirección]
                            #   HOY: ports/mod.rs importa tipos del feature audit (dependencia invertida).
                            #   OBJETIVO: los tipos viven en domain/models.rs; ports solo los referencia.
```

**Frontend (`frontend/src/`)**: ya está modular por `features/` con cero imports
cruzados. No se reestructura; solo se alinea al backend (un `api/` por feature,
como ya hace auth).

---

## 3. Reglas de frontera (HARD)

| # | Regla | Sanción |
|---|---|---|
| 1 | Un módulo de dominio NUNCA importa otro módulo de dominio | La secuencia fluye por `domain/models.rs` + archivos en disco |
| 2 | `modules` → `domain` y `modules` → `infrastructure` permitido | Dependencia solo hacia abajo |
| 3 | `domain` y `infrastructure` NUNCA importan `modules` | Prohíbe el ciclo |
| 4 | `domain` solo depende de crates externos (serde, chrono, thiserror) | Nada del proyecto, nada de Tauri |
| 5 | Los casos de uso que cruzan módulos viven en `app`, no dentro de un módulo | Orquestación explícita y visible |
| 6 | Los comandos Tauri son delegados finos | Cero lógica de negocio en `app` |
| 7 | El conocimiento de dominio vive en UN solo lugar | Tablas WMO, paths, recálculo de campos: una fuente única |

**Verificación**: `cargo modules` o un script de CI puede fallar el build si
se viola la regla 1 (grep de `use crate::modules::` cruzados).

---

## 4. Contratos de datos entre módulos

| Contrato | Produce | Consume | Estado actual |
|---|---|---|---|
| `DayRecord` (meta + horas {datos, synop, calculado} + cli embebido) | synoptic | cli, monthly_summary, audit, app | Implícito en JSON **sin `schema_version`** — archivos viejos ilegibles |
| `CliRecord` (cli3074/4074/5074) | cli | monthly_summary, audit | Embebido en el día + escritura separada (riesgo de lost-update) |
| `MonthlyKpis` | monthly_summary | app (UI/export) | Implícito en `resumen_<st>_<per>.json` |
| `AuditMark`, `Correction` | audit | app (reportes), infrastructure (persistencia) | Definidos en el feature audit → **mover a domain** |
| `AppError` | cualquiera | todos | Mitad `Result<T,String>`, mitad `Result<T,AppError>` → unificar |

Reglas de contrato:
- Serde derive vive en `domain/models.rs`: todos serializan la misma forma.
- Todo contrato persistido lleva `schema_version` + migrador one-shot.
- Los campos derivados (pres_nmm, punto_rocio, tendencia...) se **recalculan al
  cargar, nunca se confían del archivo** (política única — hoy hay 3 copias
  que ya divergieron).

---

## 5. Plan de migración incremental (rama `refactor/modular-monolith`)

Cada fase termina con build verde (cargo check + tests) y un commit propio.
El código viejo se mueve en bloques, no se reescribe.

| Fase | Acción | Resultado |
|---|---|---|
| **0** | ✅ Esqueleto: `app/`, `domain/`, `modules/` con fronteras documentadas | Estructura objetivo visible, nada roto |
| **1** | `domain/errors.rs`: mover AppError, unificar los `Result<T,String>` restantes | Un solo tipo de error |
| **2** | `infrastructure/storage`: extraer paths ARCA + backups + escritura atómica de `json_handler/utils.rs`; unificar "synop"/"synoptic" | Un solo dueño del filesystem |
| **3** | `modules/synoptic`: mover lógica de día + cálculos; unificar las 3 políticas de recálculo en una | synoptic independiente |
| **4** | `modules/cli`: mover `json_handler/cli.rs`; **borrar cli_autofill.rs**; tablas WMO → `domain/wmo` | cli independiente, duplicación eliminada |
| **5** | `modules/auth`: mover `auth.rs`; tokens CSPRNG; converger a AppError | auth independiente |
| **6** | `ports` + `domain/models.rs`: los tipos de audit salen del feature → domain; adapters dependen solo de ports | Hexagonal con dirección correcta |
| **7** | `app/`: comandos finos por módulo; la orquestación (audit×synoptic, export) sube a app | Capa de aplicación delgada |
| **8** | Borrar muertos: `summary.rs` + tabla `summary_logs`, `cli_autofill.rs`, `validate_user_role`, `get_observations_list` (roto) | Árbol limpio |

Criterio de salida de cada fase: `cargo check`, `cargo test`, `cargo clippy -D warnings`
y los 70 tests de frontend siguen verdes.

---

## 6. Qué NO se hace

- **No** mover `monthly_summary` ni `audit` de su ubicación actual (ya son módulos
  correctos; moverlos solo agrega ruido al diff).
- **No** migrar observaciones a SQLite (el archivo de día es la unidad de
  intercambio del dominio; ver informe de datos).
- **No** introducir un framework de microservicios ni separar procesos.
- **No** refactorizar lógica interna durante la migración: mover primero,
  mejorar después (cada módulo se mejora independientemente UNA VEZ migrado).
