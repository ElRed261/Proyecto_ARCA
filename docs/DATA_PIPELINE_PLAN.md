# Plan — Extensión de Ingeniería de Datos (ARCA Pipeline)

> Fuente: `docs/Proyecto_ARCA_PRD.md` y `docs/Proyecto_ARCA_TRD.md` (Agosto 2026).
> Este documento analiza esos requisitos, los contrasta con buenas prácticas
> de ingeniería de datos (Medallion Architecture, Airflow Best Practices,
> data quality y modelado dimensional) y define el plan de ejecución.

> **Estado al 2026-08-19 — rama `arca-pipeline`**: pipeline implementado en `pipeline/` (ver §3). 35 tests aprobados, `ruff check` sin incidencias, venv en `/tmp/opencode/pipeline-venv`. Fases 0–6 completadas (ver §4). API consultable con 5 endpoints (ver §2).

---

## 1. Análisis del PRD/TRD

### Lo que está bien planteado

- **Problema real y medible**: datos atrapados en la app local, conversión manual, sin warehouse consultable. Los objetivos O1–O5 son verificables.
- **Separación de responsabilidades**: el pipeline es un servicio externo al VPS, no dentro de la app de escritorio (TRD §3). Correcto: no acopla el motor Rust con el procesamiento batch.
- **Idempotencia mencionada**: UPSERT por `(station_id, fecha, source_file)` (TRD §2.3) — es la base correcta, aunque incompleta (ver gaps).
- **Seguridad de credenciales**: Service Account fuera del repo, permisos 600, env vars (TRD §4). Bien.
- **Detección de novedad** por `modifiedTime`/checksum (TRD §2.1) y **fallo de validación → rejected/ sin abortar** (TRD §2.2): ambas son prácticas de la industria.
- **Plan por fases con verificación** (TRD §6) y alineación con certificaciones (TRD §8).

### Gaps frente a buenas prácticas (lo que hay que agregar)

| # | Gap | Práctica faltante |
|---|-----|-------------------|
| G1 | El TRD mete `raw_json` + columnas consultables en **una sola tabla** `observations` | **Medallion**: bronze (raw + metadatos de ingesta), silver (observaciones limpias), gold (agregados mensuales). Capas separadas, nunca mezcladas |
| G2 | "Esquema mínimo" de validación sin reglas de dominio | **Data quality formal**: pandera con rangos físicos WMO (T −60..60 °C, HR 0..100, presión 850..1100 hPa) + checks post-carga (counts, duplicados, integridad) |
| G3 | UPSERT por `source_file` — si el Excel cambia pero el nombre no, no se detecta | Agregar `sha256` del contenido como parte de la clave de idempotencia: `(station, fecha, sha256)` |
| G4 | No hay migraciones versionadas del warehouse | **Alembic** + `schema_version` en los contratos persistidos (el mismo problema que ya tiene la app con sus JSON sin versionar) |
| G5 | Logs + alerta Telegram, sin métricas ni estado | Observabilidad: `last_run.json` con filas ingeridas/rechazadas/duración + endpoint de estado; alerta solo por umbral |
| G6 | Sin tests ni CI para el pipeline | Tests unitarios con fixtures reales chicos + CI que corra lint/tests/validation; prueba de idempotencia = rerun sin duplicados |
| G7 | Reusar `excel_to_json.py` tal cual | Ese script es un GUI Tkinter de 918 líneas y su schema de salida YA divergió del actual (`hum_hr/pres_alti` vs `pres_est/p3`). Extraer el núcleo de transformación como **funciones puras** con tests; descartar el GUI |
| G8 | `cron/systemd` como única orquestación | OK para MVP; para portafolio sumar **Prefect** (retries, backfill, UI, estado) — el TRD ya apunta a certificaciones DE |
| G9 | Detección por `modifiedTime` solamente | Checksum persistido en tabla de control: si el archivo cambia, reprocesar; si no, skip (evita reproceso inútil y detecta archivos reemplazados) |

---

## 2. Arquitectura objetivo (Medallion aplicado a ARCA)

```
Google Drive (Excel .xlsm)
      │ (1) poll + checksum
      ▼
BRONZE  raw/  ── archivo tal cual + _meta.json {source_file, sha256, ingested_at, drive_modified_time}
      │ (2) transform puro (núcleo extraído de excel_to_json.py)
      ▼
       ┌─ validación pandera ── falla ──▶ rejected/{motivo}.json + log
       │
SILVER  obs_limpia  ── observaciones normalizadas (una fila por estación+fecha+hora)
      │ (3) UPSERT (station, fecha, sha256)
      ▼
GOLD  kpis_mensuales  ── agregados por estación/mes (medias, extremos, conteos)
      │ (4) consulta
      ▼
FastAPI (localhost / reverse proxy) ──▶ dashboard Recharts o Metabase
      │  GET /health                                          → liveness
      │  GET /state                                           → last_run.json
      │  GET /stations/{code}/observations?from=&to=          → silver_observations
      │  GET /stations/{code}/kpis?year=&month=               → gold_kpis_mensuales
      │  GET /rejected                                        → rejected/*.rejected.json
      ▲
   Prefect (con fallback sin dependencia): retries, backoff, estado, alerta
```

Reglas de oro incorporadas (fuente: Medallion Architecture — Databricks; Best Practices — Airflow):

1. **Bronze nunca se muta**; se reprocesa desde raw en cualquier momento.
2. **Tarea = transacción**: re-ejecutar produce el mismo resultado (UPSERT, particiones fijas, nunca `now()` en lógica).
3. **Validación en el borde**, un archivo malo no aborta la corrida.
4. **Migraciones versionadas** para el warehouse; contratos con `schema_version`.
5. **Observabilidad por corrida**: estado, métricas, alerta por umbral.

### Endpoints API (implementados en `pipeline/src/arca_pipeline/api/main.py`)

| Método | Ruta | Fuente | Descripción |
|--------|------|--------|-------------|
| GET | `/health` | — | Liveness check (`{"status":"ok"}`) |
| GET | `/state` | `data/state/last_run.json` | Estado de la última corrida (o 404 si no hay corridas) |
| GET | `/stations/{code}/observations?from=&to=` | `silver_observations` | Observaciones validadas por estación y rango de fechas (ISO `YYYY-MM-DD`) |
| GET | `/stations/{code}/kpis?year=&month=` | `gold_kpis_mensuales` | KPIs mensuales por estación (404 si no existe) |
| GET | `/rejected` | `data/rejected/*.rejected.json` | Listado de archivos rechazados con motivo |

> Verificación local: `ls pipeline/src/arca_pipeline/api/` → `main.py` (FastAPI). Tests en `pipeline/tests/test_api.py`.

---

## 3. Estructura del repo (directorio real `pipeline/`)

> **Nota**: el nombre planificado `arca-pipeline/` se implementó como `pipeline/` en la raíz del repo. Toda referencia en este documento a `arca-pipeline/` debe leerse como `pipeline/`.

```
pipeline/
├── pyproject.toml            # ruff, pytest, deps (no scripts sueltos)
├── .env.template             # credenciales NUNCA en el repo
├── README.md                 # diagrama de capas + cómo correr + cómo testear
├── alembic.ini               # configuración Alembic (raíz del pipeline)
├── src/arca_pipeline/
│   ├── config.py             # settings desde env (pydantic-settings)
│   ├── contracts.py          # contratos versionados (schema_version)
│   ├── api/                  # FastAPI consultable (main.py) — ver §2 endpoints
│   ├── ingest/               # conector Google Drive: poll, checksum, control, drive
│   ├── transform/            # núcleo Excel→JSON puro + mapeo WMO (fixture 01032026.xlsm)
│   ├── validate/             # contratos pandera SilverSchema + rangos físicos WMO
│   ├── load/                 # UPSERT a PostgreSQL (silver) + agregados (gold)
│   └── orchestrate/          # runner Prefect con fallback + estado + alerta
├── migrations/               # Alembic 0001_initial (stations, silver_observations, gold_kpis_mensuales)
├── tests/                    # fixtures reales (estacion_central_01032026.xlsm) + test de idempotencia
│   └── fixtures/estacion_central_01032026.xlsm  # fixture golden — estación 78486
├── docker/                   # docker-compose (postgres 16) + Dockerfile opcional
├── sql/                      # consultas de verificación y dashboard
└── venv (no versionado)      # /tmp/opencode/pipeline-venv — entorno de ejecución local
```

Verificación: `ls pipeline/src/arca_pipeline/api/` existe y contiene `main.py`.

---

## 4. Plan por fases — estado al 2026-08-19

| Fase | Estado | Entregable | Verificación | Buenas prácticas |
|------|--------|-----------|--------------|------------------|
| **0. Fundamento** | ✅ completada | `pipeline/` + pyproject + env template + CI (ruff, pytest) | `ruff check` limpio, `pytest` 35 passed | Reproducibilidad, secrets, lint desde el día 1 |
| **1. Ingesta (bronze)** | ✅ completada | Conector Drive: poll por checksum (`ingest/control.py` + `ingest/drive.py`), descarga a `raw/` + `_meta.json`, tabla de control | Archivo + meta en raw tras corrida; skip si checksum no cambió; `test_ingest.py` | Bronze inmutable, detección por contenido (G9) |
| **2. Transform (silver)** | ✅ completada | Núcleo puro Excel→JSON extraído de `excel_to_json.py` (sin GUI) + normalización; fixture real `01032026.xlsm` (estación 78486) | JSON/schema coincide con contrato versionado; `test_transform.py` golden | Funciones puras testeadas (G7) |
| **3. Validación** | ✅ completada | Contratos pandera `SilverSchema` + rangos físicos WMO (T −60..60 °C, HR 0..100, presión 850..1100 hPa); `rejected/` con motivo | Archivo inválido → `rejected/` con log; pipeline sigue; `test_validate.py` | Fail vs reject (G2) |
| **4. Carga (warehouse)** | ✅ completada | PostgreSQL + Alembic `0001` (stations, silver_observations, gold_kpis_mensuales); UPSERT `(station_code, fecha, hora, source_sha256)` + gold | SELECT de control; **rerun no duplica**; `test_load.py` | Medallion + idempotencia por contenido (G1, G3, G4) |
| **5. Orquestación** | ✅ parcial (MVP) | Prefect con fallback sin dependencia (`orchestrate/runner.py`): poll→transform→validate→load; retries con backoff exponencial, `last_run.json` (`data/state/`), alerta por umbral | Corrida automática; fallo de red reintenta (3 intentos); estado visible; `test_orchestrate.py` | Observabilidad (G5, G8) |
| **6. Consulta/UI** | ✅ completada | FastAPI (`api/main.py`) en localhost + endpoints `/health`, `/state`, `/stations/{code}/observations`, `/stations/{code}/kpis`, `/rejected`; reverse proxy con auth pendiente | Consulta por estación/fecha/variable responde; `test_api.py` | Warehouse consultable sin exponer a internet |
| **7. Tests + docs** | 🔄 en curso | Unit/integration con fixtures reales + test de idempotencia en CI; README de arquitectura | `pytest` 35 passed; rerun sin duplicados; docs de cada capa (este plan + `pipeline/README.md`) | G6 + documentación de portafolio |

> **Leyenda**: ✅ completada y verificada en `pipeline/tests` · 🔄 parcial / en curso.
> **Evidencia 2026-08-19**: `35 passed, 4 warnings` · `ruff check` All checks passed · venv `/tmp/opencode/pipeline-venv` · rama `arca-pipeline`.

---

## 5. Stack recomendado

| Capa | Elección | Alternativa | Por qué |
|------|----------|-------------|---------|
| Lenguaje | Python 3.12 | Rust | Ecosistema DE (pandera, prefect, google-api) |
| Validación | pandera | Great Expectations | Ligero, en código, CI-friendly |
| Warehouse | PostgreSQL | SQLite ampliada | Consultas concurrentes + UI; el VPS ya lo soporta |
| Migraciones | Alembic | — | Versionado obligatorio (G4) |
| Orquestación | Prefect (local) | cron/systemd (MVP) | Retries/backfill/UI; suma al portafolio (G8) |
| Secretos | `.env` + permisos 600 | Vault | Suficiente para 1 usuario; nunca en repo |
| Export/Excel | `openpyxl`/`calamine` | — | El motor Rust ya usa calamine; el pipeline reusa el mismo formato |

---

## 6. Notas de portafolio

- El diagrama bronze/silver/gold + Prefect + Alembic + pandera + PostgreSQL cubre exactamente lo que piden roles junior/mid de Data Engineering (patrones de ingestión/transform, orquestación, almacenamiento, calidad).
- El README del pipeline debe incluir: diagrama de arquitectura, captura del estado de una corrida, y la evidencia de idempotencia (rerun sin duplicados) — es lo que más mira un recruiter.
- Alineación con certificaciones declaradas en el TRD §8: SQL/relacionales (schema + queries), AWS/GCP DE (patrones), BigDataStack (ingestión/transform).
- Futuro opcional (fuera de alcance actual): dbt para el modelado gold, Metabase para dashboards self-service, Docker para reproducibilidad total en el VPS.
