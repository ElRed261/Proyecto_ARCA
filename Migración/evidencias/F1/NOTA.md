# Evidencia F1 — Núcleo de datos Python + importador JSON→SQLite (2026-10-15)

## Hecho

- `oms_core/db/`: esquema SQLite + **migraciones numeradas** (1–5) espejando el orden
  exacto de `OLD/.../db.rs` + `sync_queue.rs::MIGATION_SQL`:
  - **M1** users / stations (+15 seed filas) / summary_logs / error_marks /
    corrections / app_config / 3 índices — SQL verbatim del oráculo.
  - **M2** DROP audit_logs / correction_requests.
  - **M3** dedupe de error_marks ANTES del índice único `uq_error_marks_slot` (R6).
  - **M4** `sync_pending` + `idx_sync_pending_unsent` (verbatim MIGATION_SQL).
  - **M5** (nuevo): tabla `observations` con `UNIQUE(station_id, fecha, hora)` y
    columnas de documento en summary_logs (`kind`/`day`/`sha256`) con
    dedupe-antes-de-índice y `uq_summary_logs_doc`, mismo patrón que M3.
  - Runner propio con `PRAGMA user_version`; una transacción por migración.
- `oms_core/db/connection.py`: `journal_mode=WAL`, `foreign_keys=ON`,
  `busy_timeout=5000` en TODA conexión (equivalente al `with_init` del pool Rust).
  La ruta de la base SIEMPRE por parámetro: nada de Tauri en el core (ADR-03,
  ADR-02: SQLite única fuente de verdad).
- Repositorios por entidad (`oms_core/db/repositories/`): `users`, `stations`,
  `observations` (nueva), `summaries` (verbatim docs), `audit`
  (error_marks + corrections con las MISMAS consultas del Rust
  `sqlite_audit_repository.rs`, incluida la barrera única → `MarkConflictError`
  con el mensaje del oráculo), `app_config` (KV), `sync` (enqueue idempotente +
  status P3.4; la pasada de retry con backoff es F7).
- `oms_core/paths.py`: cadena pura `ARCA_BASE_DIR > PathProfile (app_config
  'path_config') > Documents/ARCA`, capa `{modulo}` conservada; `validate_profile`
  con reglas y mensajes idénticos al Rust; PathProfile corrupto →
  `PathConfigError` RUIDOSO (nunca fallback silencioso, lección P1.4).
- `oms_core/importer/`: scan de ambos layouts (‘Estación Central/2025/05/’,
  ‘Estacion Central/…’ y mesi con y sin ceros), parse diario
  `{meta, horarias, resumen_dia}` + resumen `{meta, datos}`, upserts idempotentes
  por clave natural, SHA-256 por archivo origen, y reporte de verificación §6.3
  (conteos 100% + muestreo determinista ~10% campo a campo).
- `tests/`: `test_f1_migrations.py`, `test_f1_repositories.py`,
  `test_f1_importer.py`, `test_f1_paths.py` + `conftest.py`; fixtures pequeños
  copiados de OLD (4 archivos, read-only).

## Decisiones

- **D1 — observations solo horas Z.** Las filas auxiliares de `horarias`
  (TMAX/TMIN/filas_nuvosidad_*) REPITEN su etiqueta dentro de un mismo archivo
  (medido: 211×TMAX en 61 archivos), así que no pueden llevar la UNIQUE
  `(station_id, fecha, hora)`. La tabla nueva guarda solo las 8 horas sinópticas
  (`06Z`…`21Z`) con las 7 magnitudes + observador; el documento diario COMPLETO se
  conserva VERBATIM (byte a byte tras decode UTF-8) en `summary_logs`
  (`kind='diario'`, `day=D`). Cero pérdida de dato, clave natural limpia.
- **D2 — datos verbatim en summary_logs.** Los docs diario y resumen se guardan
  como el texto exacto del archivo origen + su SHA-256. El resumen documental
  queda a prueba de re-generaciones (INSERT OR REPLACE por clave natural,
  respaldado por `uq_summary_logs_doc`).
- **D3 — fechas ISO.** `observations.fecha` es `YYYY-MM-DD`; el oráculo ya filtraba
  con `fecha LIKE 'YYYY-MM-%'` en los reportes de auditoría. `meta.fecha` DDMMYYYY
  se valida con calendario real (bisiestos incluidos) espejando
  `json_handler::parse_date_parts` (P1.4: fail duro, sin defaults).
- **D4 — estaciones desconocidas: placeholder inactivo.** La clave de estación del
  importador es `meta.estacion` VERBATIM (sin matching difuso de nombres: adivinar
  mal es escribir el dato en la estación equivocada == perderlo). Si la clave no
  existe entre las 15 seed, se provisiona `stations(id=clave, is_active=0)`.
  Resultado real del corpus: se provisionaron `MDJB`, `Estacion Central`,
  `Estación Central`. La homonimia acento/no-acento queda marcada en el reporte;
  completar/marcar estación activa es trabajo de F3.
- **D5 — NaN ≡ NULL.** El corpus viejo usa `NaN` donde otros archivos usan `null`;
  SQLite guarda NaN como NULL. La normalización se aplica por igualdad en ambos
  lados del muestreo, incluido `source_sha256`.
- **D6 — verificación por corrida.** El conteo 100%/muestreo 10% se hace sobre las
  claves naturales de ESA corrida (importar una segunda raíz no "falla" por filas
  preexistentes de otra raíz; se registran como `preexisting_keys`). Claves de la
  corrida ausentes en la BD = pérdida de dato = falla dura.
- **D7 — desviación consciente en paths.** Si `ARCA_BASE_DIR` está SETEADA pero
  vacía, Rust terminaba resolviendo un `synop` relativo (env `Some("")` → saltea
  perfil Y default). Aquí esa env vacía se ignora y se sigue la cadena: el
  "escribir en el lugar equivocado es perder datos" manda sobre el bug.
- **D8 — seeding de usuarios queda en F3.** `init_db` viejo sembraba usuarios con
  bcrypt (dependencia externa); F1 es stdlib-puro, así que la tabla `users` tiene
  repositorio pero sin seed ni hashing (regla ADR-01/feature freeze; auth es F3).

## Puertas (todas verdes, local)

- `.venv/bin/pytest -q` → **75 passed** (4 de F0 + 71 de F1), cero skips.
  - RED capturado: `ModuleNotFoundError: No module named 'oms_core.db'` antes de
    implementar; errores de esquema/repos corregidos contra tests.
- `.venv/bin/ruff check oms_core oms_ui tests packaging` → limpio.
- **Corrida real de aceptación (§7-F1)** — corpus sample completo, read-only:
  - diario (61 archivos, `data/json/`): conteos **(488, 488)** obs y **(61, 61)**
    docs; 0 errores de archivo; muestreo 10% = 55 comparaciones campo a campo,
    **0 mismatches**.
  - resumen (2 archivos): conteos **(2, 2)**, 1 comparación doc verbatim, 0 mismatch.
  - Re-corrida completa: 100% idempotente (mismos conteos, 0 cambios, 0 mismatch).
  - Totales BD: 488 observaciones, 63 docs verbatim, 18 estaciones (15 seed +
    3 placeholders inactivos).
  - Reporte completo archivado: `evidencias/F1/import_report_F1.json`.

## write_guard → transacciones (equivalencia documentada)

`OLD/.../write_guard.rs` resolvía el lost-update con lockfile O_EXCL + fsync
(lock → leer → mutar → escribir). SQLite da las mismas garantías por motor:
serialización de escritor único (WAL + busy_timeout + `BEGIN IMMEDIATE`
alrededor de toda mutación multi-statement), atomicidad de transacción (nunca
queda un documento a medias) y durabilidad de commit WAL (equivalente al fsync).
Los repositorios mutan en una sola sentencia o dentro de una transacción única,
de modo que el lock ya no puede olvidarse. Nota en `oms_core/db/__init__.py`.

## DoD F1 (§6.4 PRD)

1. Limpio: ruff verde (scope F0); Python puro stdlib (sin deps nuevas).
2. Tests verdes: 75/75, sin skips.
3. Oráculo: corrida real con conteos 100% y muestreo 10% limpio (arriba);
   consultas de auditoría espejadas 1:1 del Rust.
4. PRD: sin enmienda necesaria (desviaciones D6/D7 documentadas aquí).
5. Commit: rango del padre (`neoarca(F1)`).
