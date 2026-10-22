# Evidencia F4 — Observación Sinóptica, la pantalla reina (2026-10-15)

## Hecho

| Módulo Neo Arca | Oráculo (OLD/, read-only) | Port |
|---|---|---|
| `oms_core/services/synoptic.py` | `utils/synopticUtils.js` (HOURS/EVEN/ODD, BASE/EVEN key model, `hourCompletion`, `parseFieldError`, `sanitizeSynopGroup`) + `storage.rs` (`validar_grupos_synop` mensajes EXACTOS, `build_horas_map`, `get_observation_core` flatten) + `synopticDraft.js` (P4.4) + localStorage `arca_observador_*` + `json_handler::validate_inputs` | Qt-free (ADR-03), sin Tauri |
| `oms_core/services/cli.py` | `cli3074/utils/rowUpdate.js` (`enforceOneDecimal`, `applyCliFieldUpdate`) + `cliFenomenos.test.js` caso a caso + `modules/cli/mod.rs` (`save_cli_generic`/`load_cli_generic`/`load_cli3074_json_core`) + listas de campos exactas de las 3 páginas | servicios planos |
| `oms_ui/pages/synoptic.py` | `SynopticPage.jsx` (grilla, selector de horas con progreso y tooltips, exclusiones 0CS↔56, temporada ciclónica, iX gating, `SaveConfirmModal`, diálogos de error con campo culpable + cambio de hora, Ctrl+S, Alt+1..8, observer recordado, autosave de draft, guard de cierre `beforeunload`) | PySide6 Widgets (ADR-04) |
| `tests/test_f4_{synoptic,cli,ui}.py` | 31 core/CLI + 23 pytest-qt (offscreen) | 54 nuevos |
| `Migración/evidencias/F4/oracle_F4(.py/.json)` | corrida oráculo §7-F4 sobre 2 diarios reales (78485/78486 · 08/12/2025) | nuevo |

## Decisiones

- **D1 — transacción por hora con savepoint.** `save_hour` valida estación/fecha/grupos
  y recálculo ANTES de escribir; luego un SAVEPOINT (`f4_save_hour`) envuelve el upsert
  de `observations` + la revisión del documento diario vía los repositorios F1. Como
  los repos F1 llaman `conn.commit()` tras cada upsert, el servicio les entrega un
  proxy `_NoCommitConnection` (commit no-op) y solo él libera/commitea el savepoint:
  **la fila y el documento aterrizan juntos o no aterriza nada** (la garantía del
  `validar_grupos_synop` del Rust + la equivalencia write_guard→transacciones del PRD F1).
- **D2 — el doc diario verbatim se REVISA en sitio.** La doc `{meta, horarias,
  resumen_dia}` de F1 no se regenera: se conservan `meta`/`horarias`/`resumen_dia`
  intocados y se fusiona la clave `horas` del oráculo (misma estructura `{observador,
  datos, synop, calculado}` de `build_horas_map`, con `meta.fecha` DDMMYYYY y
  `ultima_actualizacion`). El `sha256` de `summary_logs` pasa a ser el del documento
  nuevo (los docs de importación intactos conservan el SHA fuente).
- **D3 — draft: un archivo único ligado a estación+fecha.** El `sessionStorage` del
  oráculo se vuelve un archivo (`synoptic_draft.json`) en el directorio de configuración
  resuelto (`ARCA_CONFIG_DIR` env > `~/.config/neearca`), payload
  `{observations, active_hour, results_per_hour, station, fecha}`; `isDraftValidFor`
  portado igual (borrador corrupto o ajeno → ignorado). `-- config_dir` inyectable en
  test; nunca en la BD.
- **D4 — filas para las 8 horas (paridad legacy).** El oráculo guardaba las 8 filas
  `horarias` aunque la hora estuviera vacía (medido en el corpus: los 2 diarios reales
  tienen 8 filas con 7 casi vacías). El guardado F4 recorre las 8 horas de HOURS;
  una hora vacía genera fila con NULLs + entrada de doc mínima — los conteos casan
  con los del importador.
- **D5 — filas/derived por oms_calc.** `recalculate_derived_fields_json` recibe
  `correc_alt_resuelta = datos.correc_alt o str(stations.ch)` (F2 D1), y
  `nddff_anterior` sale del `Nddff` de la hora previa ya asentada en el doc (equivalente
  al lookup intradocumento de `get_observation_core`).
- **D6 — errores estructurados.** `SaveError` lleva `{detail, field, hour, stage}`
  con los mensajes del Rust por bytes (incluida la cola `\n` + 21 espacios de
  «Ejemplos válidos:…»); la UI también puede usar `parse_field_error` para el path
  del frontend.
- **D7 — exclusión 0CS↔56 + gates del oráculo.** `meteo_6_2`/`meteo_8_1` se excluyen
  mutuamente al editar; `meteo_8_1` (56 DL DM DH) se deshabilita fuera de temporada
  ciclónica (junio–noviembre) o si hay 0CS relleno; `meteo_4_6` (7wwW1W2) queda
  habilitado solo con iX∈{1,4} vía `oms_calc.should_include_weather`.
- **D8 — dirty flag solo de edición del usuario.** El guard de `closeEvent` (P4.4)
  se arma con ediciones tecleadas; la selección programática de estación/fecha
  (inicialización, captura de pantalla) cierra sin preguntar. pytest-qt cierra los
  widgets en teardown, así que el fixture de test inyecta un stub no bloqueante del
  guard; los tests del guard le dan comportamiento propio vía
  `page._draft_guard_class`.
- **D9 — ventana de captura.** `SynopticWindow` (QMainWindow) contiene la página para
  que `closeEvent` corra de verdad; `build_synoptic_window(conn, station=…, fecha=…)`
  la construye con datos de muestra (06Z real del corpus 78485) **sin mostrarla**, y
  prioriza un draft válido de la misma estación+fecha sobre la muestra.

## ⚠️ Desviación documentada — meteo_6_3 / meteo_6_4 (1snTxTxTx / 2snTnTnTn)

El oráculo muestra esas casillas (row 6, deshabilitadas en horas impares), pero la
lista de claves medida que gobierna esta fase (`BASE_DATA_KEYS` de 17 +
`EVEN_EXTRA_KEYS` de 4) NO las incluye: en el corpus legacy viven como slots
*manuales* separados (`synop_manual["1sn_tx_manual"]`, `["2sn_tn_manual"]`), que no
pasan por `to_synop_name`. La grilla F4 implementa el modelo de claves medida (17+4).
Si el equipo decide portarlas más tarde, es una casilla más en `_FIELD_LABELS` + su
clave en `BASE_DATA_KEYS` — decisión de producto, no de arquitectura.

## Matriz oráculo (oracle → test F4)

| Observador del oráculo | Test Neo Arca | Resultado |
|---|---|---|
| EVEN_HOURS / BASE (17) / EVEN_EXTRA (4) / HOUR_META | `test_hour_lists_match_the_oracle` | ✓ |
| hourCompletion denominador honesto (21 pares / 17 impares) | `test_hour_completion_honest_denominator`, `UI: test_even_only_fields…`, `UI: …progress_bar` | ✓ |
| parseFieldError («el grupo 'X' en hora YYZ») | `test_parse_field_error_portfolio` + highlight UI | ✓ |
| validar_grupos_synop >5 chars, mensaje byte-exacto, nada escrito | `test_save_hour_rejects_group_over_5_and_writes_nothing` | ✓ |
| carácter inválido con posición | `test_save_hour_rejects_invalid_group_character_with_position` | ✓ |
| Sanitize SynopGroup (solo dígitos y '/') en el widget | `UI: test_group_fields_capped…`, `test_group_validator_blocks_letters…` | ✓ |
| save_observation_json transaccional (fila + doc) | `test_save_hour_transactional_path_writes_row_and_diario_doc`, `UI: test_full_flow…` | ✓ |
| estación/fecha inválidas (mensajes del oracle) + calendario real | `test_save_hour_rejects_unknown_station…`, `test_save_usesobservation_year_calendar` | ✓ |
| P4.4 draft ligado + corrupto ignorado | `test_draft_roundtrip_and_validity`, `test_draft_corrupt_file_is_ignored`, `UI: close_event ×3` | ✓ |
| SaveConfirmModal (parciales + vacías) | `test_pre_save_review…`, `UI: test_review…` 3 | ✓ |
| campo culpable en rojo + salto a su hora | `UI: test_guilty_field_highlight_and_automatic_hour_switch` | ✓ |
| observador recordado por estación | `test_obsevar_kvs_roundtrip`, `UI: prefill ×2` | ✓ |
| fenómenos: booleanos sin formateador, hermanos intactos, sin mutar input, un decimal | `test_toggle_check…` (7 réplicas de cliFenomenos.test.js) | ✓ |
| listas de campos exactas 3074/4074/5074 + ceil humidity | `test_3074_field_lists_match_the_oracle`, `test_one_decimal_ceil_semantics` | ✓ |
| save_cli merge preserva meta/horas/hermanos | `test_save_cli3074…`, `test_save_cli_preserves_sibling_cli_keys` | ✓ |
| load_cli3074 recalcula tendencias/visibilidad/tiempo presente | `load_cli3074` (core) + contrato | ✓ |
| Ctrl+S guarda, Alt+1..8 cambia hora | `UI: keyboard ×2` (keystroke real + secuencias) | ✓ |

## Corrida oráculo §7-F4 (`oracle_F4.py` → `oracle_F4.json`)

- 2 diarios reales (78485 ch=2.0, 78486 ch=1.6, 08/12/2025): las 8 horas por fixture
  pasan por `synoptic.save_hour`.
- `datos` passthrough: **0 mismatch**; grupos `synop_manual`→`to_synop_name`:
  **0 mismatch**; recalc derived vs `calculados` legacy: **0 mismatch** (los slots
  legacy venían todos vacíos → 10 diffs «empty» explicados, nunca silenciosos);
  filas: **8 → 8 por fixture**; `pres_nmm` escrito en la hora con datos.
- **Verdict: ok=true** — diff vacío o explicado.

## Puertas

| Puerta | Resultado |
|---|---|
| `QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q` (suite completa) | **238 passed** (184 previas + 53 F4 + 1 de F3 recontados), 0 skipped, 9.1 s |
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` (ft, núcleo) | 205 passed, 2 skipped (los módulos UI, causa escrita PySide6 ft » F3-D7) |
| `.venv/bin/ruff check oms_core oms_ui tests Migración/evidencias/F4` | limpio (0 errores) |
| `cargo clippy` | **NOT RUN** — F4 no toca ni un archivo Rust (oms_calc intacto) |
| commit | NO hecho (lo reserva el padre, `neoarca(F4): …`) |
| GUI en display | ninguna corrida; todo offscreen (`offscreen` forzado en conftest) |
| captura de pantalla de la reina | NOT RUN — no solicitado; `build_synoptic_window` queda listo para el padre (offscreen) |

RED capturado: `ImportError` de `oms_core.services.cli/synoptic` (colección de los 3
módulos nuevos falló) antes de toda implementación; GREEN por pasos se listó arriba.
</content>
