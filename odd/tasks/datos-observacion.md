# Arquitectura del dato — implementación (fases A1–A6)

Implementa lo definido en `docs/ARQUITECTURA_DATOS.md`. Objetivo final del
dueño: **cargar el día 26/10/2025 debe traer todos los datos del Synop y
todos los datos de los CLI**, sin campos perdidos ni valores duplicados.

## Specs

- **S1** Una **tabla de mapeo única** en el core: cada campo es `observed`
  (se guarda) o `derived` (se recalcula al leer). Ninguna otra lista puede
  contradecirla.
- **S2** El mapeo cubre **los 44 campos de grupo** (`meteo_*`, `extra_8ns_*`)
  y los **11 datos** observados del bloque `datos`.
- **S3** `load_day_document(conn, estación, fecha)` devuelve el día completo:
  8 horas con `observador` (siempre presente), `datos`, `grupos`, **y** los
  tres bloques CLI.
- **S4** Limpieza de legado: los carriles `9spspsp_18…_24` contaminados
  (`555`, `29uuu`, textos, malformados) se descartan al leer/escribir.
- **S5** Sin derivados guardados: `calculado`, `correc_alt`, `visibilidad`,
  `hum_hr`/`hum_tvap`/`hum_ptor` no se persisten.
- **S6** Día cerrado a las 06Z del día siguiente; después sólo auditoría.

## Tasks

| ID | Specs | Qué | Estado |
|---|---|---|---|
| A1 | S1,S2,S5 | `oms_core/services/document_map.py`: tabla única + limpieza de grupos | en curso |
| A1b | S2 | Arreglar `_SYNOP_FIELD_KEYS` (faltaban `meteo_14_*`) | en curso |
| A2 | S3,S4 | `oms_core/services/document.py`: `load_day_document` + `empty_day_document` | pendiente |
| A2b | S3 | UI: hidratar sinóptica **y** los 3 CLI desde el mismo documento | pendiente |
| A3 | S5 | Guardado schema 2 + `document_versions` | pendiente |
| A4 | S6 | Cierre a 06Z + roles + justificación | pendiente |
| A5 | S4 | Migrar los 2.554 archivos con reporte de descartes | pendiente |
| A6 | — | Export schema 2 + ida y vuelta con Drive | pendiente |

## Log

- **L1** (verbatim) «Procede con los pasos y recuerda guardar el .md de
  arquietctura de los datos. Procede»
- **L2** Arquitectura de referencia ya commiteada: `docs/ARQUITECTURA_DATOS.md`
  (commit 4499af6).
