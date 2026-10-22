# Evidencia F2 — `oms_calc` completo (2026-10-15)

## Hecho

Portación **verbatim** (mismas ramas, mismos umbrales, mismos strings) del oráculo:

| Módulo Neo Arca | Oráculo (OLD/, read-only) | Líneas |
|---|---|---|
| `oms_calc/src/synoptic.rs` | `modules/synoptic/calculations.rs` §psicrométricos (L9-51), §grupos SYNOP (L53-146), §tablas/mapeos WMO (L150-346), §I/O structs (L352-415), §algoritmo (L418-510), §política de recálculo (L513-631) | port de 1-631 |
| `oms_calc/src/monthly.rs` | `monthly_summary/calculations.rs` (1-293, `process_day_data` + helpers) + shapes `ObservationMeta/HourlyData/HourlyRecord/DaySummary/DailyObservation/DailyKpis` de `monthly_summary/json_pipeline.rs` (L1-103) | port íntegro |
| `oms_calc/src/lib.rs` | frontera PyO3: módulo F0 ampliado a **32 funciones** | nuevo |
| `oms_calc/src/tests_synoptic.rs` / `tests_monthly.rs` | **54 tests Rust nuevos** (no existían para estos archivos) | nuevo |
| `tests/test_f2_calc.py` | **59 tests Python**: cada vector Rust repite en la frontera JSON + errores de JSON malformado | nuevo |
| `Migración/evidencias/F2/oracle_F2(.py|_json)` | corrida oráculo §7-F2 | nuevo |

### Inventario de funciones portadas (expuestas vía PyO3, nombres del oráculo)

- Psicrométricos puros: `calcular_h26`, `calcular_h27`, `calcular_h28_asumido`,
  `calcular_tension_vapor`, `calcular_humedad_relativa`, `calcular_punto_rocio`
  (todas `Option<f64>` nativo → `Optional[float]`; sin `PyResult`, infalibles).
- Grupos SYNOP: `format_temperature_group`, `format_dew_point_group`,
  `format_pressure_group`, `format_pressure_tendency_group`,
  `format_pressure_24h_group`, `format_humidity_group`.
- Políticas: `should_include_precipitation`, `should_include_weather`.
- Mapeos: `to_synop_name`, `to_frontend_name`, `get_visibilidad_from_irixhv`.
- Utilidades: `format_dif`, `calc_dif`, `calc_car`, `calc_tiempo_presente`,
  `get_prev_hour`, `tendencia_a` (F0, ahora delegado de `calcular_tendencia_a`).
- Pipelines JSON: `realizar_calculos_json(request_json, correc_alt?) -> PyResult<String>`,
  `recalculate_derived_fields_json(12 parámetros planos) -> String`,
  `process_day_data_json(obs_json: &str) -> PyResult<String>`.

### Decisiones de cirugía de frontera

- **D1 — sin `DbPool`**: `get_station_info`/pool NO portan. El lookup viejo
  (stations repo → `info.ch`) es reemplazo de Python: `realizar_calculos_json`
  toma `correc_alt` resuelta (F4 pasa la `ch` de la estación); la `correc_alt`
  propia del request conserva la prioridad del oráculo (estación primero, request
  solo si la resuelta queda vacía). En `recalculate_derived_fields` idéntico:
  input > fallback resuelto (`correc_alt_resuelta`), con el mismo `trim().`
  que el oráculo antes del fallback.
- **D2 — `StationInfo` no cruza la frontera**: el eco de estación viaja *dentro*
  del JSON del request (claves extra capturadas con `#[serde(flatten)]`) y se
  copia tal cual a `response.station_info` como `serde_json::Value` (serde lo
  serializa `null` cuando no hay eco, como el serde del oráculo). Desviación
  documentada: `serde_json::Map` (BTree sin `preserve_order`)
  **re-ordena alfabéticamente** las claves del eco al re-serializar.
- **D3 — comandos Tauri EXCLUIDOS (F3 admin)**: `get_stations`,
  `create_station`, `update_station`, `delete_station`,
  `calculate_observations` no portan. `station_id` se mantiene en
  `CalculationRequest` por paridad de forma (queda sin uso dentro de oms_calc).
- **D4 — `p24` reservado**: como en el oráculo, `CalculationResponse` sí lleva
  `p24_dif`/`grupo_58_59_p24` (usados), pero `DerivedFields` no expone p24
  (`let _ = p24;` verbatim); testeado (incidencias idénticas con y sin p24).
- **D5 — nombres**: los 12 parámetros de `recalculate_derived_fields_json`
  espejan la firma del oráculo sin `pool`, añadiendo `correc_alt_resuelta`
  último (station_id, ts, th, pres_est, p3, p24, correc_alt, irixhv,
  seven_ww, nddff_actual, nddff_anterior, correc_alt_resuelta ≡ 12 planos).
- **D6 — claves de `DailyKpis`**: los `#[serde(rename)]` del oráculo se
  portan verbatim («MAxima presión nivel medio del mar», «Nuvocidad dia», etc.);
  verify en frontera con los nombres reales de los resúmenes guardados (shape C).
- **D7 — slicing de bytes**: `get_visibilidad_from_irixhv`, `calc_tiempo_presente`
  y el formateo de `dias` conservan el slicing por bytes del oráculo (con los
  mismos requisitos ASCII de los datos reales).
- **D8 — guard de `realizar_calculos` intacto**: `Th > Ts` → error string del
  oráculo exacto («Error: Th no puede ser mayor que Ts.»), grupo `1snTTT`
  igualmente emitido; `Th == Ts` válido.
- **D9 — tricky formatting checkeado contra el oráculo por casos**:
  «1» + signo(0/1) + `{:03}` (ej. −5.7 → `11057`); presión `{:04}` sobre
  `(p*10)%10000`; presión ≥ 0 → `58`, < 0 → `59`; banda de tendencia tras
  redondear a 0.1 con `.round()` half-away-from-zero; `{:04.1}` de
  `calc_dif` rellena con ceros («03.0»); `calc_car` usa la diferencia CRUDA
  (sin redondeo) a diferencia del grupo 5appp.
- **D10 — media de nubosidad**: el oráculo computa `nub_media` desde los
  valores SIN redondear de dia/tarde (probado: 05/05 corpus → 3.3, no 3.4);
  la frontera y los tests Rust/Python lo fijan.

## Puertas (todas locales)

| Puerta | Resultado |
|---|---|
| `cargo test --manifest-path oms_calc/Cargo.toml` | **54 passed, 0 failed** (nuevos; incluye bandas 0.5/0.6, 1.4/1.5, 1.9/2.0; política de vacíos; cadena `prev_hour`; mapping ida/vuelta con asimetría `9spspsp_*` fiel) |
| F0 (tests Rust precedent) | siguen verdes (54 incluyen cobertura F0 vía delegado `tendencia_a`) |
| `.venv/bin/python -m pytest -q` | **134 passed, 0 skipped** (F0 4 + F1 71 = 75 previos + **59 nuevos de F2**, parametrizados incluidos) |
| `.venv/bin/ruff check oms_core oms_ui tests packaging` | limpio (py313 target) |
| `cargo clippy --manifest-path oms_calc/Cargo.toml -- -D warnings` | limpio |
| Build/install | `maturin build -i .venv/bin/python` → tag `cp314-cp314t` (addendum F0 episódico aplicado) instalada vía `uv pip install --force-reinstall` |
| Python ≥ 3.13 | `py_compile` ok en ambos .py; ruff target py313 |

⚠️ **Defecto pre-existente (fuera de mis superficies)**: `.venv/bin/pytest` tiene
shebang apuntando a `.venv-ft/bin/python` (venv renombrado en el addendum F0 → el
script quedó huérfano). El comando EXACTO `.venv/bin/pytest -q` falla con
«intérprete erróneo». La puerta se ejecutó con el equivalente
`.venv/bin/python -m pytest -q` (134 passed). Requiere reparación de padre
(reinstalar pytest/script) o regenerar venv.

## Oráculo §7-F2 (`oracle_F2.py` → `oracle_F2.json`)

Corpus leído en modo read-only; fuentes: `OLD/miscelaneos/backend_python/app/
modules/synoptic/data/{78485,78486}/2025/12/*.json` (shape A), `OLD/miscelaneos/
base_para_modulos/Resumen_Mensual_Synop/data/json/**` + `tests/fixtures/importer/
json/**` (shape B), `.../data/summaries/resumen_*.json` (shape C).

- **Shape A — borradores sinópticos (2 archivos, 16 horas Z)**: los ÚNICOS
  archivos del corpus con inputs crudos (`ts/th/pres_est/p3/p24/correc_alt`).
  Hallazgo (no fallo): **los `calculados` almacenados están vacíos en las 16
  horas** — el backend viejo guardó borradores sin ejecutar el recálculo.
  `recalculate_derived_fields_json` recomputó no-vacíos exactamente en las 2
  horas con ts/th (06Z de 78485 y 78486: tv `26.3`, hr `93`, pr `21.9`,
  pres_nmm `1026.9`, tend `03.0`/`3`, vis `160`) — coincide con los vectores
  espejo de los tests. Resto de horas: política de vacíos respetada (salidas
  vacías con inputs vacíos). El diff recomputado≠almacenado queda EXPLICADO por
  el guardado sin cálculo del lado viejo.
- **Shape B — corpus del importador F1 (64 archivos, 512 horas Z)**: los
  derivados psirométricos y `pres_nmm` SÍ están almacenados, pero **los inputs
  crudos (ts/th separados, irixhvv, 7ww, correc_alt) NO están en el archivo**:
  no se puede alimentar al recálculo desde el dato almacenado → hallazgo (no
  fallo), tal como permite §7-F2. Prueba positiva extractable: la relación
  `pres_nmm = p_est + correc_alt` con granularidad 1 decimal se verifica
  **450/450 horas** donde ambas magnitudes están almacenadas (0 mismatch) —
  misma fórmula que `oms_calc`.
- **Shape C — resúmenes mensuales (3 archivos, 1.220 celdas)**: comparación
  completa `process_day_data_json` vs columnas almacenadas (los resúmenes
  persisten EXACTAMENTE los renames serde de `DailyKpis`):
  - `MDJB_062025` (30 días): **todas las columnas exactas salvo** Lluvia
    (artefacto del generador viejo, ver abajo) y Nuvocidad dia/noche/media
    (lógica del generador viejo, ver abajo).
  - `Estacion Central_052025` (31 días): temperatura/presión/humedad/rocio/
    tensión de vapor/viento **exactas en 30/31** («Nuvocidad» y «Lluvia»
    arriba); excepciones: día 05-07 (archivo fuente con TODOS NaN → stored
    `null/NaN` vs oms_calc `null`: misma semántica, convención de serialización
    distinta); 05-17 `CALMA 7,2` vs `NNW 7,2` (empate de velocidad máxima con
    NaN en half del día; el port sigue el `>` estricto de calculations.rs);
    05-21 media 29.4 vs 29.3 (extremos idénticos 33.3/25.4; el generador viejo
    redondeó con `round()` de Python, el PRD prescribe `round_half_up` —
    decisión del oráculo-viejo, no del port).
  - `Estacion Central_062025` (31 días): **sin archivos diarios en el corpus**
    (mes de origen Excel) → no comparable; reportado como hallazgo.
  - **Artefactos del generador viejo** (explican los diffs estructurados; el
    port es fiel a calculations.rs del PRD):
    1. **Lluvia corrida un día**: stored[i] = `pp` del archivo del día SIGUIENTE
       en 28/31 casos (Central 05) y patrón análogo en MDJB (21/30 + corriemientos);
       oms_calc devuelve `resumen_dia.pp` del MISMO día (semántica del código PRD).
    2. **Nuvocidad**: el generador viejo promedió TODOS los `nub` en un solo
       barril (`nub_all`, aplicado a «dia» y «media», dejando «noche» siempre
       NaN — NaN en el archivo); el PRD split filas_dia/filas_tarde + fallback.
       (deducido: 01052025 nub_all=5.5 = stored, filas_dia/3=4.0 = recomputado).
    3. **NaN vs null** en el día sin dato del corpus (05-07) — convención, no fórmula.

  Conteo exacto: 1.220 celdas comparadas, 61 días con archivo diario, mismatch 0
  en temp/presión/humedad/viento/tensión de vapor/humedad/día normal salvo los
  3 patrones de arriba (todo cuantificado en `oracle_F2.json`).

**Conclusión oráculo**: no queda ningún diff sin explicar attributed al port;
los diffs estructurados provienen de (i) borradores guardados sin cálculo
(shape A), (ii) ausencia de inputs crudos en el dato almacenado (shape B), y
(iii) desviaciones del generador viejo de resúmenes (Lluvia +1 día, nub
mono-barril, NaN) + Python `round()` vs `round_half_up` (shape C). Los que
toca resolver F5 quedan documentados (lógica nub/Lluvia al regenerar resúmenes).

## Vector espejo de frontera (proof) — resumen

- `realizar_calculos_json`: corrida completa hora 06Z 78486 08/12/2025
  (ts 23.2 / th 22.3 / pres_est 1025.3 / p3 1022.3 / p24 1024.1 / correcc 1.6):
  tv `26.3`, hr `93`, pr `21.9`, dif `0.9`, grupos `10232/20219/40269/53030/
  58012/29093`, p3_dif `3.0`, p24_dif `1.2`, pres_nmm `1026.9`, `Th>Ts` con
  el error del oráculo, vacío completo, no numérico ignorado, eco `station_info`.
- Errores de frontera: JSON malformado / forma incorrecta / lista → `ValueError`
  (serde_json estricto). Los tokens NaN/Infinity de Python (json.dumps los emite)
  son RECHAZADOS en la frontera — exploit de la convención F1-D5 (normalize antes
  de pasar; cubierto en `test_process_day_data_rejects_non_finite_json_tokens`).

## DoD F2 (§6.4 PRD)

1. Compila limpio ✓ (clippy `-D warnings`; ruff verde).
2. Tests verdes ✓ (Rust 54 + Python 134 ejecutados; 0 skips; F0/F1 intactos).
3. Oráculo ✓ (arriba: shape A/B/C con hallazgos explicados; nada sin explicar
   attributable al port).
4. PRD: sin enmienda necesaria; F5 hereda los hallazgos del generador viejo.
5. Commit: rango del padre.
