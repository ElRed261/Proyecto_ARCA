---
tags: [arca, trd, tecnico, arquitectura, ingenieria-datos, pipeline]
---

# TRD — Proyecto ARCA (extensión Data Pipeline)

> Technical Requirements Document
> Autor: Andry Emiliano (ElRed261)
> Fecha: Agosto 2026
> Estado: Propuesta

## 1. Arquitectura objetivo

```
Google Drive (Excel)
      │  (1) API download
      ▼
[Ingestion Service]  ── temporal/VPS
      │  (2) trigger transform
      ▼
[Transform Module]  ── reusa script Excel→JSON (oculto)
      │  (3) validado
      ▼
[Warehouse]  ── PostgreSQL/SQLite en VPS
      │  (4) consulta
      ▼
[Query/UI Layer]  ── SQL o web ligera
      │
   Orchestrator (cron/systemd) cicla (1)→(4) cada X
```

## 2. Componentes

### 2.1 Ingestion Service
- Lenguaje: Python 3.12 (ya en VPS) o Rust si se integra al motor.
- Lib: `google-api-python-client` + `google-auth`.
- Auth: Google Service Account (JSON credentials) en env seguro, NO en repo.
- Detección de novedad: comparar `modifiedTime` o checksum contra última corrida.
- Reintentos: exponential backoff (3 intentos).

### 2.2 Transform Module (oculto)
- Reutiliza el script actual `excel_to_json.py` (ya existe en ARCA/miscelaneos/scratch).
- Se ejecuta como subproceso o import interno tras descarga.
- Salida: JSON estructurado compatible con el esquema de ARCA.
- Validación: esquema mínimo (station_code, fecha, campos WMO obligatorios).
- Fallo de validación → mover a `rejected/` con log, no abortar pipeline.

### 2.3 Warehouse
- Motor: PostgreSQL (recomendado para concurrencia/consulta) o SQLite ampliada si se prefiere ligereza.
- Esquema propuesto:
  ```sql
  stations(id PK, code UNIQUE, name, ...)
  observations(
    id PK,
    station_id FK,
    fecha DATE,
    raw_json JSONB,        -- payload completo
    temp_seca, punto_rocio, presion_nmm, ...  -- columnas consultables
    source_file TEXT,
    ingested_at TIMESTAMP
  )
  audit_events(...)
  ```
- Índices: `(station_id, fecha)`, `(fecha)`.
- Idempotencia: `UPSERT` por `(station_id, fecha, source_file)` para no duplicar.

### 2.4 Query / UI Layer
- Opción A: acceso SQL directo (psql / cliente) desde VPS.
- Opción B: API ligera (FastAPI) + frontend mínimo con Recharts para dashboard.
- Puerto expuesto solo en localhost o tras auth/reverse proxy (Caddy/Nginx).

### 2.5 Orchestrator
- `systemd` timer o `cron` cada X (ej. `0 */6 * * *` = cada 6h).
- Script wrapper: corre ingesta→transform→carga; escribe `last_run.json` y log.
- Alerta en fallo: log + notificación Telegram (vía bot o webhook).
- Estado: endpoint/JSON con última corrida y próxima.

## 3. Integración con ARCA existente

- El motor Rust de ARCA YA tiene `calculations.rs`, `json_handler`, `db.rs` (SQLite).
- El pipeline nuevo es un **servicio externo al VPS**, no dentro de la app de escritorio.
- Sincronización: el warehouse del VPS es la fuente consultable; la app sigue para registro manual/auditoría local.
- Futuro: la app puede leer del warehouse vía API para mostrar histórico.

## 4. Seguridad

- Credenciales Google: archivo `credentials.json` fuera del repo, permisos 600, en `/home/erebus/.secrets/`.
- Variables de entorno para DB y tokens; nunca hardcodeadas (ver Plan_Implementacion Fase 1).
- Warehouse no expuesto a internet sin auth.
- Auditoría: log de quién/qué se cargó.

## 5. Requisitos no funcionales

- Latencia ingesta→warehouse: < 5 min para un Excel típico.
- Disponibilidad: pipeline corre autónomo; fallo no detiene la app de escritorio.
- Mantenibilidad: cada componente en su propia carpeta del repo `arca-pipeline/`.
- Observabilidad: logs por corrida + estado visible.

## 6. Plan de implementación (fases)

| Fase | Entregable | Verificación |
|------|-----------|--------------|
| 1 | Conector Google Drive descarga Excel | Archivo en temporal tras corrida |
| 2 | Transform oculto Excel→JSON validado | JSON coincide con esquema ARCA |
| 3 | Carga idempotente a warehouse | SELECT cuenta filas; rerun no duplica |
| 4 | Query/UI consultable | Consulta por estación/fecha responde |
| 5 | Orchestrator cron + alertas | Corrida automática cada X; fallo avisa |

## 7. Dependencias

- Python: `google-api-python-client`, `google-auth`, `pandas`, `openpyxl`, `sqlalchemy`, `psycopg2` (si PostgreSQL).
- Sistema: `systemd` o `cron` en VPS Oracle.
- Red: acceso saliente a `googleapis.com` desde VPS.

## 8. Relación con certificaciones de Andry

Este pipeline ejercita directamente lo de:
- IBM SQL y DB Relacionales 101 → esquema warehouse, SQL.
- AWS/GCP Data Engineer → orquestación, almacenamiento en nube.
- BigDataStack (DE) → patrones de ingestión/transform.
- GitHub Foundations → repo `arca-pipeline/`, conventional commits.
