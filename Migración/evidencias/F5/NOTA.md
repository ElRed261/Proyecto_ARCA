# Evidencia F5 — Resumen mensual + Excel (2026-10-15)

## Hecho

| Módulo Neo Arca | Oráculo (OLD/, read-only) | Port |
|---|---|---|
| `oms_core/services/summary.py` | `monthly_summary/json_pipeline.rs` (shapes `DailyObservation`/`DailyKpis` con los 21 renames verbatim, `analyze_files` flujo adapt + `_cor` + ordenación, `save/load/list_summary_history`, política `process_day_data`) + `synop_adapter.rs` (adaptación del JSON sinóptico reciente: horas 8 + cli3074/cli4074 + TMAX/TMIN + filas dia/tarde + `LL_24h→LL`, resolución Nddff→8NhCLCMCH) + `config.rs`/`excel_reader.rs` (mapeo xlsx) + `commands.rs` (superficie generate/load/history/export/delete) | Qt-free (ADR-03); `calculations.rs` NO reimplementado (frontera F2 `process_day_data_json`) |
| `oms_core/services/excel_export.py` | `json_pipeline.rs::export_to_excel` (21 headers verbatim en negrita, números como números, strings como strings, nulls vacíos) | openpyxl |
| `oms_ui/pages/summary.py` | `features/summary` (selector estación/mes/año, Generar, historial, tabla, exportar, indicador de correcciones) | QTableView + QAbstractTableModel, 21 headers verbatim |
| `oms_core/db/repositories/summaries.py` | extendido (no reescrito): + `delete_doc` por clave natural | 1 función |
| `oms_ui/main_window.py` | página `summary` cableada (era placeholder) | 4 líneas |
| `tests/test_f5_{summary,excel,ui}.py` | réplicas pytest/pytest-qt por superficie | 30 tests |
| `Migración/evidencias/F5/oracle_F5(.py/.json)` | corrida oráculo §7-F5: 3 meses regenerados + diff por columna | nuevo |

## Partida parcial heredada (qué se conservó / reescribió)

El worker anterior dejó `summary.py` + `excel_export.py` + `pages/summary.py` +
3 suites + los retoques a `summaries.py`/`main_window.py` (todo sin commit).
Veredicto tras lectura + corrida (26/26 verdes entonces) + contraste oráculo:

- **Conservado**: arquitectura general, los 21 headers verbatim, `generate_month`
  por docs `kind='diario'` + overlay de correcciones aprobadas + recálculo oms_calc,
  `kind='mensual'` sin colisión con `resumen`, historial list/load/delete,
  export openpyxl, página Qt completa (selectores, progreso inline, historial,
  modelo 31×21, export, indicador), retoques `summaries.py`/`main_window.py`.
- **Corregido**: `observation_from_doc` ignoraba los bloques `cli3074`/`cli4074`
  y no derivaba filas de nubosidad desde `horas` (un día puro-F4 caía al
  mono-barril `nub_all`, contra el adapt del oráculo) → ahora orden cli4074 →
  horas → legacy + filas dia/tarde legacy-si-existen si-no-derivadas (5 tests
  RED→GREEN nuevos); `_apply_legacy_correction` perdía la corrección en días sin
  `horarias` → ahora materializa la fila (1 test); 2 errores ruff B008
  (`QModelIndex()` en defaults → `None`); 1 import muerto; 1 test UI duplicado
  idéntico eliminado.

## Decisiones (producto, vinculantes — ya decididas por el usuario)

- **P1 — Lluvia en su propio día.** El generador viejo corría `pp` un día
  (`stored[i] = pp[i+1]`, verificado 23/31+9/30 celdas). Neo Arca guarda el `pp`
  del día. Diff esperado y cuantificado (`rain_shift`).
- **P2 — split real dia/tarde con fallback documentado.** El viejo promediaba
  TODOS los `nub` en un barril (`dia == media`, `noche` siempre NaN — 55+90+93
  celdas con esa firma). Neo Arca: filas dia (AST 5/8/11) / tarde (14/17/20),
  cli4074 primero, luego Nddff→8NhCLCMCH por hora; sin filas, `nub_all`
  (heredado de `oms_calc`, F2-D10: media desde mitades SIN redondear).
- **P3 — NaN ≡ null** (F1-D5): normalizado en `_num`, en el muestreo y en el
  diff del oráculo. El día 07/05 (fuente todo-NaN) regenera nulls.
- **P4 — `round_half_up`** (heredado de `oms_calc`, port del `calculations.rs`
  del oráculo): el `round()` Python del generador viejo queda como diff
  documentado (05-21: media 29.3 vs 29.4 con extremos idénticos).
- **P5 — mes calendario completo.** El viejo contaba archivos (`total_dias` =
  nº ficheros); Neo Arca emite los 28/30/31 días con nulls donde no hay diario.
  Diff estructural documentado (nunca por celda).

## Desviaciones documentadas (no son bugs)

- **D1 — tabla de 21, no "31×20".** El PRD §7-F5 dice 31×20 pero el oráculo tiene
  21 columnas; se implementan las 21 verbatim (typos incluidos: `MAxima`,
  `Nuvocidad`). El PRD no necesita enmienda (el §7-F5 ya dice "tabla 31×20 con
  QTableView" como aproximación; la evidencia manda 21).
- **D2 — sin error "mes sin datos".** El oráculo fallaba sin archivos; Neo Arca
  devuelve el mes en nulls (testeado, `test_generate_month_all_null_month…` y
  flujo UI MDJB/febrero). Decisión consciente: la pantalla nunca rompe.
- **D3 — `total_dias`/meta con formato propio.** `periodo` MM/YYYY (el legacy
  columna usa MMYYYY sin barra), `generado` RFC3339 local, `total_dias`
  calendario (P5). El doc legacy columna `{meta,data}` no se imita: el nuestro
  es `{meta,datos}` filas como el `save_summary` del oráculo Rust.
- **D4 — delete borra la fila DB**, no manda a la papelera del SO (`trash::delete`
  del oráculo). El mensaje UI conserva el texto ("papelera").
- **D5 — validación de estación por clave**, sin `validate_inputs` Tauri: mes
  inválido → `SummaryError{stage: validate}`; estación con `/` o `\` → error.
- **D6 — fecha DDMMYY de 6 chars no adaptada.** El oráculo la expande; nuestros
  docs siempre son DDMMYYYY validados en escritura (F1-D3/F4): entrada inalcanzable.
- **D7 — slicing de grupos por chars, no bytes.** F2-D7 exige ASCII; los grupos
  reales lo son; equivalente observado.
- **D8 — openpyxl no declarado en `pyproject.toml`** (`dependencies = []`).
  Instalado en `.venv-gil` (3.1.5); el `.venv` ft lo salta por `importorskip`.
  Declararlo es empaquetado (F8, superficie del padre).
- **D9 — correcciones nub sobre filas legacy.** Los campos de corrección nub no
  existen en `_LEGACY_HORA_DATA_KEYS` (el overlay legacy solo toca valores
  HourlyData almacenados); correcciones Nddff en docs con filas legacy no
  mueven dia/tarde (limitación conocida, sin test que la exija).

## Matriz oráculo (oracle → test F5)

| Observador del oráculo | Test Neo Arca | Resultado |
|---|---|---|
| 21 renames serde verbatim (+ typos) | `test_export_sanity_header_fingerprint`, shapes | ✓ |
| `analyze_files` adapt ×2 formas + sort DDMMYYYY | legacy JSON / F4 `horas` / xlsx import | ✓ |
| lluvia día propio (P1) | `Lluvia == 5.0` día 15, `== 4.2` día xlsx | ✓ |
| split dia/tarde + fallback (P2) | filas legacy, derivadas de Nddff, cli4074>horas, `nub_all` fallback, F2-D10 5.2 | ✓ |
| NaN→null (P3) | día 07 todo-NaN, `_num`, muestreo | ✓ |
| round_half_up (P4) | 4.333→4.3, media 5.2, caso 05-21 en oráculo | ✓ |
| mes calendario + nulls (P5) | 31/28 filas, `Dias` ISO completo | ✓ |
| `save_summary` sin colisión kind | `mensual` vs `resumen` importado conviven | ✓ |
| history sort período desc | `list_history` [(MDJB,06),(EC,05)] | ✓ |
| load ausente → None; delete idempotente | roundtrip incl. doble delete False | ✓ |
| `_cor` → overlay aprobado (pendiente ignorado) | legacy pres_est, recompute `th` vía oms_calc, aislamiento por día | ✓ |
| overlay materializa hora ausente | fila creada con 1015.0 | ✓ |
| excel_reader config exacta | sheets/rows/cols, B3>filename, filename fallback, G37, tolera 4074/1200Z ausentes | ✓ |
| export números/str/nulls + relectura | tipos openpyxl + roundtrip generado | ✓ |
| UI: selectores/generar/tabla/historial/export/overlay | 6 tests pytest-qt offscreen | ✓ |

## Corrida oráculo §7-F5 (`oracle_F5.py` → `oracle_F5.json`)

- **Mayo 2025** (4+27 JSON diarios, claves con/sin acento unidas por día
  —merge que prefiere la fila con datos— vs `resumen_Estacion Central_052025`,
  651 celdas): **570 exactas**, 23 `rain_shift`, 55 `nub_artifact` (firma
  noche-null + dia==media verificada por celda), 1 `input_version` (05-07:
  fuente actual todo-NaN → nulls correctos; el `VRB` almacenado viene de otra
  versión del fichero), 1 `wind_tie` (05-17 `CALMA 7,2` vs `NNW 7,2`, empate de
  máxima con `>` estricto del oráculo, hallazgo F2 heredado), 1 `rounding`
  (05-21, hallazgo F2 heredado). **0 UNEXPLAINED.**
- **Junio 2025 MDJB** (30 JSON vs `resumen_MDJB_062025`, 630 celdas):
  **531 exactas**, 90 `nub_artifact`, 9 `rain_shift`. **0 UNEXPLAINED.**
- **Junio 2025 Central xlsx → NO comparable (drift de plantilla).** Los 31
  `*.xlsm` del corpus son una revisión más nueva que el `ExcelConfig`
  congelado: datos en C..N (B = subíndice de hora) mientras `config.rs` lee
  B..M. El port verbatim decodifica absurdos físicos (p_est 12.5, v 252 m/s,
  nub 8/17); el resumen almacenado se construyó con libros de plantilla
  anterior, hoy ausentes. Se reporta con evidencia por celda (`template_drift`
  485; se conservan las firmas del generador viejo: 24 `rain_shift`, 93
  `nub_artifact`, 49 exactas) — mismo tratamiento que F2 dio a este mes
  ("origen Excel → no comparable"). Adaptar el importador a la plantilla nueva
  DIVERGIRÍA del oráculo: fuera de alcance.
- **Estructural** (por mes, no por celda): meta `{estacion,periodo MMYYYY,
  registros}` vs `{estacion, periodo MM/YYYY, total_dias calendario, generado}`;
  almacenado Junio-xlsm trae 31 filas con el 06-22 duplicado (dos libros por el
  split de acento; el viejo los listó ambos) vs 30 calendario (el diario hace
  upsert por fecha: último importado gana).
- **Excel end-to-end** (mes MDJB regenerado → openpyxl): headers verbatim +
  negrita, 31 filas, `2025-06-01`, tmax número, dirección string, nulls vacíos.
- **Verdict: ok** — 0 celdas UNEXPLAINED en meses comparables + Excel verificado.

## Puertas

| Puerta | Resultado |
|---|---|
| `QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q` (suite completa) | **269 passed** (239 previas + 30 F5), 0 skipped |
| `.venv-gil` ruff | **NOT RUN** — ruff no instalado en ese venv; se usó `.venv/bin/ruff` (mismo árbol, 0.17.0) |
| `.venv/bin/ruff check oms_core oms_ui tests Migración/evidencias/F5` | limpio (0 errores; B008 del parcial corregido) |
| `cargo clippy` | **NOT RUN** — F5 no toca ni un archivo Rust (oms_calc intacto) |
| GUI en display | ninguna corrida; todo offscreen (forzado en conftest) |
| commit | NO hecho (lo reserva el padre, `neoarca(F5): …`) |

RED capturado: 5 tests nuevos fallaron antes del fix (`cli4074`/`cli3074`/
`pure_doc`/`materializes`: filas dia/tarde ausentes en días puro-F4 y overlay
perdido en hora ausente); GREEN tras la reescritura del adapt (17/17 módulo,
269 suite). El duplicado UI se eliminó (26→25 heredados + 5 nuevos = 30 F5).
