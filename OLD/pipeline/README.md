# arca-pipeline

Batch data pipeline meteorological: baja `.xlsm` desde Google Drive, los transforma a JSON,
los valida (pandera, rangos físicos WMO), los carga a PostgreSQL de forma idempotente y
calcula KPIs mensuales. Orquestado con Prefect.

## Arquitectura medallion

```
bronze (raw + metadatos)  ->  silver (validadas)  ->  gold (agregados)
     |                            |                        |
 ingest (Drive)           validate (pandera)       load (KPIs)
     |                            |                        |
     +---- control + rejected/ ---+                        +
                              PostgreSQL (Alembic)
```

Capas nunca mezcladas: cada paquete bajo `src/arca_pipeline/` declara sus fronteras en el
docstring del módulo (qué hace, qué produce, qué consume, qué NO importa).

## Estructura

```
pipeline/
├── pyproject.toml
├── .env.template
├── src/arca_pipeline/
│   ├── config.py              # pydantic-settings
│   ├── contracts.py           # contratos versionados
│   ├── ingest/                # Drive + control file
│   ├── transform/             # .xlsm -> JSON (núcleo puro)
│   ├── validate/              # pandera en el borde
│   ├── load/                  # silver UPSERT + gold KPIs
│   └── orchestrate/           # flow Prefect
├── migrations/                # Alembic (env.py; alembic.ini llega con la primera migración)
├── sql/                       # verify.sql, kpis.sql
├── tests/
└── docker/                    # docker-compose.yml (postgres 16)
```

## Cómo correr

```bash
docker compose -f docker/docker-compose.yml up -d     # Postgres local
cp .env.template .env                                # completar credenciales
uv venv && uv pip install -e ".[dev]"                # o: python -m venv .venv && pip install -e ".[dev]"
alembic upgrade head                                 # aplicar migraciones (requiere alembic.ini)
python -m arca_pipeline.orchestrate.runner           # una corrida del pipeline
```

## Cómo testear

```bash
pytest
ruff check .
```

## Reglas del pipeline

- **Idempotencia**: re-correr un archivo ya ingestado es un no-op. El sha256 del fuente
  es parte de la clave única `(station_code, fecha, hora, source_sha256)`; control file evita
  re-descargas.
- **Validación en el borde**: pandera valida antes de entrar a silver; lo que falla va a
  `rejected/`, jamás a silver.
- **Secrets**: todo en variables de entorno / `.env` (`.env` no se versiona). Nunca en código.
- **Migraciones versionadas**: los cambios de schema pasan por Alembic.
- **Observabilidad**: cada corrida escribe `last_run.json` (archivos, rechazados, duración).

## Evidencia

**Estado de una corrida** — formato de `data/state/last_run.json`:

```json
{
  "started_at": "2026-08-21T13:00:02+00:00",
  "finished_at": "2026-08-21T13:00:44+00:00",
  "duration_s": 41.7,
  "files_ingested": 3,
  "files_rejected": 1,
  "rows_loaded": 288,
  "rejected": 1
}
```

**Idempotencia (rerun sin duplicados)** — verificado por `tests/test_load.py::test_upsert_idempotent_rerun`
y reproducible contra una base real:

```bash
python -m arca_pipeline.orchestrate.runner          # corrida 1: ingesta y carga
python -m arca_pipeline.orchestrate.runner          # corrida 2: files_ingested=0, rows_loaded=0
psql ... -c "SELECT count(*), count(DISTINCT (station_code, fecha, hora, source_sha256))
             FROM silver_observations;"             # counts iguales => sin duplicados
```

La segunda corrida reporta `files_ingested: 0` porque el checksum de cada archivo ya está
registrado; un archivo cuyo contenido cambie (nuevo sha256) sí se reprocesa.