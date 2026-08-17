# Plan — Extensión de Ingeniería de Datos (ARCA Pipeline)

> Fuente: `docs/Proyecto_ARCA_PRD.md` y `docs/Proyecto_ARCA_TRD.md` (Agosto 2026).
> Este documento analiza esos requisitos, los contrasta con buenas prácticas
> de ingeniería de datos (Medallion Architecture, Airflow Best Practices,
> data quality y modelado dimensional) y define el plan de ejecución.

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
FastAPI (localhost/reverse proxy) + dashboard Recharts o Metabase
      ▲
   Prefect (o cron MVP): retries, backoff, estado, alerta
```

Reglas de oro incorporadas (fuente: Medallion Architecture — Databricks; Best Practices — Airflow):

1. **Bronze nunca se muta**; se reprocesa desde raw en cualquier momento.
2. **Tarea = transacción**: re-ejecutar produce el mismo resultado (UPSERT, particiones fijas, nunca `now()` en lógica).
3. **Validación en el borde**, un archivo malo no aborta la corrida.
4. **Migraciones versionadas** para el warehouse; contratos con `schema_version`.
5. **Observabilidad por corrida**: estado, métricas, alerta por umbral.

---

## 3. Estructura del repo (nuevo directorio `arca-pipeline/`)

```
arca-pipeline/
├── pyproject.toml            # ruff, pytest, deps (no scripts sueltos)
├── .env.template             # credenciales NUNCA en el repo
├── README.md                 # diagrama de capas + cómo correr + cómo testear
├── src/arca_pipeline/
│   ├── config.py             # settings desde env (pydantic-settings)
│   ├── ingest/               # conector Google Drive: poll, checksum, estado
│   ├── transform/            # núcleo Excel→JSON puro + mapeo WMO
│   ├── validate/             # contratos pandera (schema + rangos físicos)
│   ├── load/                 # UPSERT a PostgreSQL (silver) + agregados (gold)
│   └── orchestrate/          # runner Prefect (o cron) + estado + alerta
├── flows/                    # definiciones de flujo (si Prefect)
├── migrations/               # Alembic (versionado del warehouse)
├── tests/                    # fixtures reales chicos + test de idempotencia
├── docker/                   # docker-compose (postgres) + Dockerfile opcional
└── sql/                      # consultas de verificación y dashboard
```

---

## 4. Plan por fases

| Fase | Entregable | Verificación | Buenas prácticas aplicadas |
|------|-----------|--------------|----------------------------|
| **0. Fundamento** | `arca-pipeline/` + pyproject + env template + CI (ruff, pytest) | CI verde en GitHub | Reproducibilidad, secrets, lint desde el día 1 |
| **1. Ingesta (bronze)** | Conector Drive: poll por checksum, descarga a `raw/` + `_meta.json`, tabla de control | Archivo + meta en raw tras corrida; skip si checksum no cambió | Bronze inmutable, detección por contenido (G9) |
| **2. Transform (silver)** | Núcleo puro Excel→JSON extraído de `excel_to_json.py` (sin GUI) + normalización | JSON/schema coincide con el contrato versionado | Funciones puras testeadas (G7) |
| **3. Validación** | Contratos pandera: schema + rangos físicos WMO; `rejected/` con motivo | Archivo inválido → rejected/ con log; pipeline sigue | Fail vs reject (G2) |
| **4. Carga (warehouse)** | PostgreSQL + Alembic: bronze/silver/gold; UPSERT `(station, fecha, sha256)` | SELECT de control; **rerun no duplica** | Medallion + idempotencia por contenido (G1, G3, G4) |
| **5. Orquestación** | Prefect (o cron MVP): poll→transform→validate→load; retries, backoff, `last_run.json`, alerta por umbral | Corrida automática; fallo de red reintenta; estado visible | Observabilidad (G5, G8) |
| **6. Consulta/UI** | FastAPI en localhost + reverse proxy con auth; endpoint de estado; dashboard Recharts o Metabase | Consulta por estación/fecha/variable responde | Warehouse consultable sin exponer a internet |
| **7. Tests + docs** | Unit/integration con fixtures; test de idempotencia en CI; README de arquitectura | `pytest` verde; rerun sin duplicados; docs de cada capa | G6 + documentación de portafolio |

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
