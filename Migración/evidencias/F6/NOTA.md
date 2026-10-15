# Evidencia F6 — Auditoría + migración legacy + UI (2026-10-15)

## Hecho

| Módulo Neo Arca | Oráculo (OLD/, read-only) | Port |
|---|---|---|
| `oms_core/services/audit.py` | `audit/service.rs` (month_name_to_num, datos/calculado maps, months_core, migrate_legacy_month_dirs_core, load_observation_with_audit_core con auto-mark + overlay + recálculo, export_corrected_json) + `audit/commands.rs` (browse stations/years/months/days, load/mark/unmark/note/propose/report/export/person-summary/migrate) + `sqlite_audit_repository.rs` vía repos F1 (mismas queries) | Qt-free (ADR-03) |
| `oms_core/services/access.py` | retocado (no reescrito): `audit` pasa a `("admin", "control_calidad")` — boundary enforced (F6-D1) | 1 matriz + docstring |
| `oms_ui/pages/audit.py` | `features/audit/pages/AuditPage.jsx` (wizard 4 pasos + breadcrumbs + back + reporte) | QListWidgets + QStackedWidget |
| `oms_ui/pages/audit_observation.py` | `AuditObservationPage.jsx` (grilla 8 horas, mark/unmark/note/propose/export, auto-alerta observador) | grid QLineEdit read-only + 2 diálogos |
| `oms_ui/pages/audit_report.py` | `AuditReportPage.jsx` (tabs detailed\|person, filtros estación/año/mes, notas inline + generales) | QTabWidget + QTableWidgets |
| `oms_ui/main_window.py` | retocado: página `audit` cableada (era placeholder) | 4 líneas |
| `tests/test_f6_{audit,ui}.py` | réplicas pytest/pytest-qt por superficie | 27 tests |
| `tests/test_f3_{access,ui}.py` | retocados por F6-D1 (encargado pierde `audit`) | 3 líneas |
| `Migración/evidencias/F6/oracle_F6(.py/.json)` | corrida oráculo §7-F6: reportes sobre marks DB semilla + migración sobre copias | nuevo |

## Decisiones (producto, vinculantes donde se indica)

- **F6-D1 — boundary ENFORCED para `audit` (discrepancia resuelta, flag al usuario).**
  OLD `Sidebar.jsx` muestra Auditoría a `[admin,administrador,encargado,control_calidad]`
  pero OLD `App.jsx` `RoleRoute /audit` exige `['admin','control_calidad']`: un
  encargado con deep-link era expulsado por el guard aunque viera la entrada.
  Se implementa la lectura estricta (encargado DENEGADO, como el guard de ruta) en
  `access.py` + servicio (`require_audit_role`) + las 3 páginas (`denied`) + nav.
  ⚠️ **FLAG PARA EL DUEÑO — una línea: keep-deny (defecto, recomendado) o
  open-to-encargado (volver `audit` a `("admin","encargado","control_calidad")`
  en `access.py` + revertir los 3 retoques F3/F6).**
- **F6-D2 — propose `pendiente` + approve explícito.** El oráculo auto-aprobaba
  dentro de `audit_propose_correction` (`estado='aprobado'`, `aprobado_por=self`),
  con lo que la puerta approve no era testeable. Aquí `propose_correction` crea
  `pendiente` y `approve_correction(id, aprobado_por)` lo pasa a `aprobado`. La
  página de observación conserva el click único del oráculo ("Aplicar Corrección"
  = propose+approve en una transacción de UI); el gate separado queda cubierto a
  nivel servicio (round-trip mark→propose→approve→export).
- **F6-D3 — load lee el diario de SQLite, browse del FS.** `browse_*` espeja los
  comandos (base dir por parámetro + conteos DB); `load_observation_with_audit`
  lee el documento `kind='diario'` de `summary_logs` (ADR-02: SQLite fuente de
  verdad) y lo aplana a la vista del oráculo (`get_observation_core`: datos +
  synop→frontend + calculado→`pr/tv/hr/dif` renames + observador con fallback a
  meta). El overlay solo aplica `aprobado`; el recálculo psicrométrico reescribe
  la vista (nunca el doc almacenado).
- **F6-D4 — export verbatim de rutas.** Original
  `{base}/{station_fs}/{yyyy}/{mm}/{station_fs}{DDMMYYYY}.json` → copia en
  `{dir}/correcciones/{station_id}{DDMMYYYY}_cor.json` (station_id SIN normalizar
  en el nombre `_cor`, como el oráculo), escritura atómica (tmp + rename),
  `meta.ultima_actualizacion` sellada, original jamás tocado (testeado por bytes).
- **F6-D5 — migración EXACTA al oráculo, tests solo sobre copias tmp.**
  Rename-si-ausente / merge-sin-pisar / rmdir-solo-si-vacío / idempotente. Los
  tests y el oráculo construyen su árbol en `tmp_path`/tempdir: OLD/ y los
  originales nunca se tocan (regla de la tarea, verificada por diseño: ninguna
  ruta fuera de tmp en `test_f6_*` ni `oracle_F6.py`).

## Desviaciones documentadas (no son bugs)

- **V1 — `role=None` = llamante ya autorizado.** Cada mutación acepta
  `role=None` (uso interno/UI ya gateada); con rol dado se exige con el mensaje
  exacto del oráculo («No autorizado: privilegios insuficientes»). `migrate`
  exige `admin` (como el comando).
- **V2 — validación de fecha más estricta en load.** El export espeja el split
  `YYYY-MM-DD` del oráculo; el load añade calendario real (F1-D3/F4: bisiestos).
- **V3 — `unmark` sobre id inexistente devuelve True** (el `DELETE` del oráculo
  tampoco verifica filas: `Ok(true)` incondicional).
- **V4 — grilla de observación curada (33 campos + labels ES)**, no los ~60 del
  JSX: el modelo de claves medido F4 (17+4) + instrumentales + 5 derivados
  read-only + observador. Los `9sp` extra no portan (misma frontera que F4-D9).
- **V5 — `default_base_dir()`** (`ARCA_BASE_DIR/synop` > `~/Documents/ARCA/synop`)
  solo para cablear la página en `main_window`; tests e importador inyectan tmp.

## Matriz oráculo (oracle → test F6)

| Observador del oráculo | Test Neo Arca | Resultado |
|---|---|---|
| month_name_to_num es/en + None | `test_month_name_to_num…` | ✓ |
| maps datos/calculado verbatim | `test_frontend_field_mappers…` | ✓ |
| browse stations/years/months(puro)/days+conteos | `test_browse_…`, `…_counts_come_from_db` | ✓ |
| overlay aprobado gana, pendiente ignorado | `test_load_…_approved_overlay` | ✓ |
| auto-mark «Falta nombre de observador»/«Sistema de Calidad», sin duplicados | `test_load_…_auto_marks…` | ✓ |
| día ausente → error | `test_load_…_missing_day_raises` | ✓ |
| barrera única → «Este campo ya está marcado como error» | `test_mark_duplicate…` | ✓ |
| unmark arrastra correcciones del slot | `test_unmark_removes…` | ✓ |
| note round-trip | `test_note_update_roundtrip` | ✓ |
| propose pendiente → approve fija estado+aprobado_por | `test_propose_starts_pending…` | ✓ |
| round-trip export con valor corregido + original intacto | `test_mark_propose_approve_export_roundtrip` | ✓ |
| report orden fecha-DESC/hora-ASC + join corrección | `test_error_report_hand_computed…` | ✓ |
| person summary + orden por errores desc | `test_person_summary_hand_computed…` | ✓ |
| migración rename + merge-sin-pisar + idempotente | `test_migrate_…` ×2 | ✓ |
| encargado denegado (servicio + wizard + obs + nav) | `test_encargado…`, `test_wizard_denied…`, `test_observation_denied…`, `test_main_window_hides…` | ✓ |
| wizard 4 pasos + back | `test_wizard_navigates…`, `…_back_button…` | ✓ |
| obs: horas + marks + mark/propose/export real | `test_observation_hour_grid…`, `…_mark_propose_export_flow` | ✓ |
| report: tabs + filtros + notas + note→DB | `test_report_tabs…`, `test_report_note_edit…` | ✓ |

## Corrida oráculo §7-F6 (`oracle_F6.py` → `oracle_F6.json`)

- **Reportes** (DB semilla 3 marks + 2 corrections vía `seed_report_fixture`):
  detailed `[(06-11 06Z pendiente 21.0→21.5), (06-10 06Z aprobado 20.0→20.5),
  (06-10 12Z sin corrección)]` + person `{auditor@x: 2/1/1, otro@y: 1/1/0}`
  — **exacto a los valores hand-computed** (`report_ok`, `person_ok`).
- **Migración** (árbol fixture COPIADO a tmp, nunca originales): before 5
  ficheros → `{"renamed_dirs": 1, "moved_files": 1}` → after con `a.json`
  renombrado, `keep.json` conservando el contenido nuevo, `extra.json` movido,
  legacy no-vacío preservado; re-run `{"renamed_dirs": 0, "moved_files": 0}`
  con árbol idéntico (`migration_ok`).
- **Verdict: ok** — 0 diffs sin explicar.

## Puertas

| Puerta | Resultado |
|---|---|
| `QT_QPA_PLATFORM=offscreen .venv-gil/bin/python -m pytest -q` (suite completa) | **296 passed** (269 previas + 27 F6), 0 skipped |
| `.venv/bin/ruff check oms_core oms_ui tests Migración/evidencias/F6` | limpio (0 errores; el E902 inicial era este dir antes de crear el oráculo) |
| `ruff format --check` (mis 11 ficheros) | limpio (el drift repo-wide es preexistente: 28 ficheros sin formatear en HEAD) |
| `cargo clippy` | **NOT RUN** — F6 no toca ni un archivo Rust (oms_calc intacto) |
| GUI en display | ninguna corrida; todo offscreen (forzado en conftest) |
| OLD/ u otras superficies | intactos (`git status`: solo 4M + 7?? en las superficies F6) |
| commit | NO hecho (lo reserva el padre, `neoarca(F6): …`) |

RED capturado: `ModuleNotFoundError: oms_core.services.audit` (+ páginas) en los
26 tests nuevos antes de implementar; tras GREEN, 2 fallos reales guiaron el
diseño (meta sin observador para el auto-mark; FK exige station ids seed).
