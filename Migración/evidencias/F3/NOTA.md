# Evidencia F3 — Auth, roles y estaciones (2026-10-15)

## Hecho

| Módulo Neo Arca | Oráculo (OLD/, read-only) | Port |
|---|---|---|
| `oms_core/services/auth.py` | `modules/auth/mod.rs` (login_user_logic, SessionStore, require_role, hash/verify DEFAULT_COST, DUMMY_HASH timing equalizer) + `db.rs::init_db` seed + `shared/utils/auth.js` (normalizeRole) | contrato observable 1:1 |
| `oms_core/services/stations.py` | `modules/synoptic/calculations.rs::get_stations/create_station/update_station/delete_station` (L623-646) → `repositories/stations_repo.rs` (funciones planas Python sobre el repo F1; los wrappers Tauri quedan atrás) | CRUD verbatim + deactivate suave |
| `oms_core/services/access.py` | `shared/components/Sidebar.jsx` MODULES + dashboard scope (§9 regla 5) | matriz de páginas + scope |
| `oms_ui/login_dialog.py` | login UI (error inline, sin popups) | nuevo |
| `oms_ui/main_window.py` | Sidebar rail: 6 entradas filtradas por rol vía access.py; contenido en QStackedWidget | esqueleto |
| `oms_ui/pages/stations_admin.py` | era `StationAdminTable`: tabla + crear/editar/desactivar | nuevo |
| `tests/test_f3_{auth,access,stations,ui}.py` | `tests/auth_flow.rs` espejado + matriz completa | 50 tests nuevos |
| `oms_core/db/repositories/users.py` | extendido (no reescrito): + `count_users` para seed | 1 función |

## Decisiones

- **D1 — errores como excepciones.** El oráculo devuelve `Err(String)`; aquí
  `AuthError` (credenciales/sesión) y `PermissionError` (require_role) llevan los
  MENSAJES EXACTOS del oráculo: «Usuario o contraseña incorrectos», «La cuenta de
  usuario está desactivada», «Sesión expirada», «Sesión no encontrada o inválida»,
  «No autorizado: privilegios insuficientes».
- **D2 — reloj inyectable.** `SessionStore(clock=...)` permite testear la expiración
  de 8h (TTL `28800`, vence con `>` estricto, como el oráculo) sin dormir; producción
  usa `time.time`.
- **D3 — contraseñas de seed con `secrets` (desviación consciente).** El oráculo
  generaba las claves del primer inicio con un xorshift sembrado con el reloj
  (predecible). Se conserva alfabeto y longitud (12, sin 0/O/1/l/I) pero con el
  CSPRNG del SO. `primer_inicio.txt` con la plantilla exacta; idempotente: con
  usuarios existentes no toca nada (tabla users no vacía → no-op, archivo intacto).
- **D4 — estaciones: delete dura ESPEJADA, deactivate suave NUEVA.** El oráculo
  tiene `update_station` Y `delete_station` (DELETE físico); el servicio porta ambos
  tal cual — `delete_station` sobre una estación con observaciones/auditoría falla
  por las barreras FK (mismo esquema, `foreign_keys=ON`). La UI de F3 usa
  `deactivate_station` (`is_active=0`) para no dejar huérfanos; testea ambas rutas.
- **D5 — alias 'administrador'.** `normalize_role` (minúsculas + 'administrador'→'admin')
  se aplica en `require_role` y `can_access`, replicando `auth.js`; el rol original
  viaja intacto en la sesión.
- **D6 — pytest-qt en la UI, `importorskip` documentado.** El módulo UI de tests
  salta con causa escrita («PySide6 not installed in this interpreter») en el venv
  free-threaded; ver D7.

## ⚠️ D7 — Restricción de toolchain: PySide6 no corre bajo CPython 3.14t

PySide6 6.12.0 solo publica wheels `cp310-abi3` (ABI del GIL). Verificado
empíricamente: importar `PySide6.QtWidgets` bajo `.venv` (3.14.7 free-threaded)
produce **SEGFAULT** (los módulos limited-API no son compatibles con el build ft).
No existe wheel `cp314t`. Consecuencia, documentada y acotada:

- **`.venv-gil`** (nueva, repo root, CPython 3.14.7 GIL de `/usr/bin/python3.14`):
  PySide6 6.12.0 + pytest + pytest-qt + bcrypt + wheel `oms_calc` reconstruida
  (`maturin develop`, `cp313-abi3`). **La suite completa (184) corre aquí.**
- **`.venv`** (ft, intocada como fuente de verdad F0-F2): bcrypt instalado;
  `python -m pytest -q` → **174 passed, 1 skipped** (módulo UI, causa escrita).
  `pytest-qt` se retiró de este venv: el plugin exige un binding Qt en el arranque
  y rompía TODA la corrida.
- La suite nunca abre ventana: `QT_QPA_PLATFORM=offscreen` forzado en
  `tests/conftest.py` (y en cada corrida).

## Matriz oráculo (auth_flow.rs + Sidebar.jsx → tests F3)

| Observador del oráculo | Test Neo Arca | Resultado |
|---|---|---|
| login exitoso → token 64-hex + sesión válida (email, rol) | `test_login_exitoso…`, `test_tokens_de_sesion_son_csprng_unicos` | ✓ |
| password incorrecta → «Usuario o contraseña incorrectos» | `test_login_fallido_con_password_incorrecta` | ✓ |
| email desconocido → UN verify contra hash dummy (timing igualado) | `test_timing_equalization…` (spy sobre `auth.verify`, NO wall-time) | ✓ |
| usuario inactivo no loguea («desactivada») | `test_usuario_inactivo_no_puede_loguear` | ✓ |
| validate_session token ajeno → «Sesión no encontrada» | `test_validate_session_rechaza_token_fuera_de_sesion` | ✓ |
| logout invalida el token | `test_logout_invalida_el_token` | ✓ |
| expirada se elimina del store + sweep en login (R5) | `test_sesion_expirada…` (reloj inyectado), `test_sweep_expired…` | ✓ |
| require_role: admin pasa, observador rechazado («privilegios insuficientes») | `test_require_role_admite_admin_y_rechaza_observador` | ✓ |
| alias 'administrador' ≡ 'admin' (auth.js) | `test_require_role_acepta_alias_administrador` + matriz access | ✓ |
| Sidebar: audit=[admin,administrador,encargado,control_calidad]; seguridad=[admin,administrador] | matriz 4 roles × 6 páginas (24 casos) + UI `test_nav_filtrada_por_rol` (5 roles) | ✓ |
| §9.5 dashboard: admin/control_calidad ven todo, el resto su estación | `test_scope_all…`, `test_scope_estacion…`, `test_scope_sin_estacion…` | ✓ |
| get/insert/update/delete stations (calculations.rs L623-646) | `test_get_stations…`, `test_create_station_roundtrip`, `test_update_station_sobrescribe…`, `test_delete_station…` (+FK) | ✓ |
| app_config `assigned_station` KV | `test_assigned_station_kv_roundtrip` | ✓ |
| seed 4 usuarios + `primer_inicio.txt` solo en primera corrida | `test_seed_admin_crea…`, `test_seed_admin_es_idempotente`, `test_seed_admin_con_usuarios_preexistentes…` | ✓ |

Diff no vacío contra el oráculo: **ninguno sin explicar** (D3 passwords, D4 delete
espejada, D5 alias — todos arriba).

## Puertas

| Puerta | Resultado |
|---|---|
| `.venv-gil/bin/python -m pytest -q` (suite completa, offscreen) | **184 passed, 0 skipped** (134 previas + 50 F3), 8.7 s |
| `.venv/bin/python -m pytest -q` (ft, suite core) | 174 passed, 1 skipped (UI, D7) |
| `.venv/bin/ruff check oms_core oms_ui tests packaging` | limpio (0 errores) |
| `cargo clippy -D warnings` | **NOT RUN** — F3 no toca `oms_calc` (ni un archivo Rust cambiado) |
| commit | NO hecho (lo reserva el padre, `neoarca(F3): …`) |
| GUI en display | ninguna corrida; solo offscreen |

RED capturado antes de implementar: `ModuleNotFoundError: No module named
'oms_core.services'` + colección fallida de los 4 módulos de test nuevos; los
statuses finales observados tras GREEN se listan arriba.

## DoD F3 (§6.4 PRD)

1. Limpio ✓ (ruff verde; sin cambios Rust → clippy N/A).
2. Tests verdes ✓ (184/184 en .venv-gil; sin skips sin causa escrita).
3. Oráculo ✓ (matriz arriba; auth_flow.rs espejado caso a caso).
4. PRD: sin enmienda necesaria; D7 es una restricción del ecosistema PySide6,
   documentada para F4 (la UI seguirá corriendo sus tests en `.venv-gil`).
5. Commit: rango del padre.
