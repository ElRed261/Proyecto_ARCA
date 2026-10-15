# Evidencia F7 — Dashboard, mantenimiento y sync (2026-10-15)

## Hecho

| Módulo Neo Arca | Oráculo (OLD/, read-only) | Port |
|---|---|---|
| `oms_core/services/sync.py` | `sync_queue.rs` (`enqueue_pending` + `SyncRow`, `get_sync_status_core`, `retry_pending_sync_core` con flag force + backoff `min(2^attempts,60)` min, `emit_after_save_core` + `emit_dual_after_save` contra raíces offline/online del PathProfile) | Qt-free (ADR-03); reloj/transporte inyectables + ganchos cooperativos |
| `oms_core/services/sync_thread.py` | (no existe en el oráculo: el retry corría en comandos Tauri) | `SyncWorker(QThread)`: stop flag + señales `progress`/`outcome`, cero acceso UI |
| `oms_ui/pages/maintenance.py` | `MaintenancePage.jsx` (PathCard por raíz con probe honesto ✓/✗, panel sync, botón de migración legacy) + `pathsService.js` | PySide6 Widgets |
| `oms_ui/pages/dashboard.py` | `DashboardPage.jsx` (centro de operaciones: tarjetas por estación, estado de hoy, lock por rol, badge de sync) | PySide6 Widgets |
| `oms_ui/main_window.py` | cableado real de las 6 entradas (era esqueleto F3 + placeholders F4–F6) | sin placeholders |
| `tests/test_f7_sync.py` + `tests/test_f7_ui.py` | réplicas pytest/pytest-qt por superficie | 54 tests nuevos |
| `Migración/evidencias/F7/oracle_F7(.py/.json)` | corrida oráculo §7-F7 | nuevo |

## Decisiones

- **F7-D1 — `SyncWorker` vive en `oms_core` (excepción ADR-03, documentada).**
  La tarea exige `oms_core/sync_thread.py` (o `services/`); ADR-03 prohíbe Qt
  en `oms_core`. Conciliación: el worker NO contiene lógica ni toca UI — abre
  su propia conexión, corre `services/sync.retry_pending_sync` con ganchos y
  devuelve el resultado por señales. Toda decisión (backoff, dedupe, errores)
  sigue testeable sin GUI en `services/sync.py`. El import PySide6 es de
  módulo (como en `oms_ui`); los tests lo cubren con `importorskip`.
- **F7-D2 — fallo de `emit` deja `last_error` (desviación exigida por la
  tarea).** El oráculo solo encolaba en silencio; aquí la fila queda con
  `last_error` + timestamps (attempts intacto: un fallo fresco no hace
  backoff y el próximo retry la toma enseguida). El panel la muestra.
- **F7-D3 — gate de backoff verbatim del oráculo (`attempts > 0`).**
  La fórmula estricta `now < last_attempt + min(2^0,60)min` daría 1 min de
  espera a filas con `attempts == 0`; el oráculo solo aplica la ventana con
  `attempts > 0` (inalcanzable con `last_attempt` seteado en el oráculo).
  Se implementa el gate exacto; testeado (`test_retry_first_attempt…`).
- **F7-D4 — tarjeta de backups con spinbox, no con probe.** El oráculo solo
  mostraba 3 PathCards; `backups_max_age_days` es un número, no una ruta
  (0 = sin definir). 3 PathCards + tarjeta numérica, todo desde PathProfile.
- **F7-D5 — strings de UI en español verbatim del oráculo**
  (`✓ carpeta escribible`, `✗ no escribible: …`, `Sincronizados: N`,
  `Tu estación: …`); código y comentarios en inglés (regla de la tarea).
- **F7-D6 — auditoría en pestañas.** La entrada `audit` del nav es un
  `QTabWidget` (Revisar = wizard F6, Reporte = report F6); la página de
  observación (necesita estación+fecha) abre como diálogo desde el wizard
  (`on_open_day`). Migración legacy corre sobre `{offline}/synop`
  (misma base que `audit.default_base_dir`), admin-gated en UI
  (`access.can_access(role, "admin")`) y re-exigido por el servicio.
- **F7-D7 — `waitSignal` de este pytest-qt no bloquea solo.**
  `qtbot.waitSignal(sig, timeout)` como sentencia suelta devuelve el
  blocker sin esperar (4 tests en rojo por ello); patrón usado:
  `blocker = qtbot.waitSignal(...); start(); blocker.wait()` o
  `qtbot.waitUntil(estado_final)`. Sin `time.sleep` en ningún test.

## Matriz oráculo (oracle → test F7)

| Observador del oráculo | Test Neo Arca | Resultado |
|---|---|---|
| `INSERT OR IGNORE` dedupe `(module, station, path)` | `test_enqueue_dedupes_like_the_oracle` (+ F1 intacto) | ✓ |
| backoff `2^attempts` min, tope 60 (attempts 1→2 … 6+→60) | `test_backoff_window_matches_oracle_schedule` (9 casos) | ✓ |
| skip dentro de ventana / corre pasada (incl. cap 60) | `test_retry_skips_inside_window…` (7 ventanas × dentro/fuera) | ✓ |
| `force=true` procesa todo ahora | `test_force_bypasses_the_backoff_window` | ✓ |
| fallo → attempts+1 + last_error; éxito drena | `test_failing_root_retries_then_drains_on_success` | ✓ |
| contenido idéntico online → synced SIN reescribir | `test_identical_online_content…` (mtime intacto) | ✓ |
| source ausente → registrado, nunca raise | `test_missing_source_is_recorded_never_raised` | ✓ |
| `emit_after_save` sin online = no-op honesto | `test_emit_after_save_without_online_root…` | ✓ |
| dual copia + limpia cola; fallo encola con error | `test_emit_after_save_copies…`, `…_failure_stays_queued…` | ✓ |
| dual resuelve PathProfile; `ARCA_BASE_DIR` = no-op | `test_emit_dual_after_save_…` ×3 | ✓ |
| PathCard probe ✓/✗ honesto | `test_probe_*` ×3 (dir nuevo, fichero, vacío + click) | ✓ |
| panel sync (pendientes, error, retry→hilo, progreso) | `test_maintenance_sync_panel…`, `…_retry_now_goes_through_the_thread` | ✓ |
| migración legacy admin-gated sobre base configurada | `test_maintenance_migration…`, `…_admin_gated` | ✓ |
| hilo: stop flag + señales; error DB como dict | `test_worker_stop_flag…`, `…_broken_database…` | ✓ |
| UI nunca se congela durante sync | `test_sync_never_freezes_the_event_loop` (ticks > 0) | ✓ |
| dashboard: alcance por rol + lock + badge | 5 tests (`test_admin_sees…`, `…_locked…`, `…_banner…`, `…_badge…`, `…_navigate…`) | ✓ |
| MainWindow: páginas reales por rol, sin placeholders | 3 tests (admin 6, observador 4, shortcut navega) | ✓ |

## Corrida oráculo §7-F7 (`oracle_F7.py` → `oracle_F7.json`)

- **Backoff** (reloj determinista, raíz simulada): attempts 1–7 →
  ventanas 2/4/8/16/32/60/60 min; **7/7 skip-dentro + run-fuera**.
- **Failing root → drain**: `outage #1` (attempts=1) → skip a +1 min →
  `outage #2` (attempts=2) → cura a +5 min → `attempted/uploaded/
  marked = 1/1/1`, bytes idénticos online, **pending 0 / synced 8**.
- **Hilo + responsiveness** (QThread real, offscreen, 25×512 KiB):
  **3019 event ticks durante la op, 11.1 ms, 25/25 synced**.
- **Verdict: ok** — 0 diffs contra el schedule del oráculo.

## Puertas

| Puerta | Resultado |
|---|---|
| `QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q` (suite completa) | **350 passed** (296 previas + 54 F7: 34 core + 20 UI), 0 skipped |
| `.venv/bin/ruff check oms_core oms_ui tests Migración/evidencias/F7` | limpio |
| `ruff format --check` (mis 8 ficheros) | limpio |
| `cargo clippy` | **NOT RUN** — F7 no toca ni un archivo Rust (oms_calc intacto) |
| GUI en display | ninguna corrida; todo offscreen (forzado en conftest + script) |
| OLD/ u otras superficies | intactos (`git status`: solo 1M + 7?? en superficies F7) |
| commit | NO hecho (lo reserva el padre, `neoarca(F7): …`) |

RED capturado: `ModuleNotFoundError: oms_core.services.sync` en colección de
`test_f7_sync.py` con el módulo ausente (restaurado → 34/34); los 4 tests de
hilo fallaron primero por el patrón `waitSignal` sin `.wait()` (F7-D7) y por
un assert desactualizado (12→25 filas); GREEN tras el fix (20/20).
Preservación: suites F1–F6 intactas (350/350 incluye sus 296).

## DoD F7 (§6.4 PRD)

1. Limpio ✓ (ruff verde en las 4 superficies; sin cambios Rust → clippy N/A).
2. Tests verdes ✓ (350/350, sin skips).
3. Oráculo ✓ (arriba: schedule 7/7 + drain + hilo con ticks medidos).
4. PRD: sin enmienda necesaria (F7-D1…D7 documentadas aquí).
5. Commit: rango del padre.
