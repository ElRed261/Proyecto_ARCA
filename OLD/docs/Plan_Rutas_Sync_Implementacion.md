# Plan de Implementación — Rutas de Guardado Configurables + Sync Online/Offline

**Fecha:** 2026-08 · **Baseline:** v2.1.0, rama `arca-pipeline`
**Feature doc:** `odd/tasks/rutas-guardado-configurables.md` (EN — mirror Engram `odd/rutas-guardado-configurables/tasks`)
**Regla de oro de testing:** todos los tests se escriben ANTES o JUNTO al código que validan
(RED→GREEN para cambios de comportamiento). Prohibido: marcar checks sin checks verdes,
debilitar/desactivar tests, saltarse suites, o reportar "pasa" sin evidencia real del runner.

---

## Principio de diseño

```
SAVE → [1] validar + lock del archivo-día
     → [2] escribir OFFLINE (raíz local configurada) con fsync+rename
     → [3] intentar escribir ONLINE ( carpeta sincronizada por Drive Desktop )
           ├─ OK    → registrar "synced"
           └─ FALLA → encolar en SQLite `sync_pending` (NO se pierde nada)
     → [4] retry programado (startup + timer + botón manual) con skip por sha256
```

La ruta "online" es una carpeta local cualquiera (p. ej. `~/GoogleDrive/ARCA/`) que
Drive Desktop sincroniza hacia la nube. ARCA no habla con la API de Drive: escribe
archivos en esa carpeta. Si Drive Desktop está caído o la carpeta no responde, el
paso 3 falla y la cola garantiza la emisión posterior — offline-first real.

---

## P1 — Configuración central de rutas (backend)

Tareas (cada una termina en work-unit commit en la feature branch `rutas-guardado`):

| # | Tarea | Criterio de verificación |
|---|---|---|
| P1.1 | Módulo `paths_config.rs`: struct `PathProfile { offline_root, online_root: Option<String>, backups_dir, summaries_dir }`, persistida como JSON en `app_config` key `path_config`; comandos `get_path_config`, `set_path_config` (solo admin), `probe_path` (crea carpeta, prueba escritura/borrado atómico, devuelve `writable: bool + error`) | `cargo test paths_config` verde |
| P1.2 | Cadena de resolución de raíces: `ARCA_BASE_DIR` (tests) > `path_config` > default `Documents/ARCA/{modulo}`. Todos los escritores (synoptic, cli, monthly_summary) la usan. `monthly_summary` deja la raíz ajena `Documents/Proyecto_ARCA/…` y pasa a `{offline_root}/{modulo_resumen}` conservando lectura-compatible con la raíz legacy | test `resolve_prefers_config_over_default`, `resolve_env_override_wins`, `summary_root_unified_and_legacy_readable` |
| P1.3 | Fix fallback Windows: la función de fallback es **pura** (`documents_or_f(head)`) y en Windows agrega `Documents`; test directa sin Tauri | test `windows_fallback_appends_documents` |
| P1.4 | Hard-fail de fechas: `parse_date_parts` devuelve `Result` — una fecha malformada **errora** (Nunca default silencioso 2025/12), tanto en save como en read | test `invalid_date_hard_fails` |
| P1.5 | Normalización de código de estación: lowercase al guardar y al indexar (colisión case-insensitive Windows/macOS) | test `station_code_normalized_case_insensitive` |
| P1.6 | `migrate_legacy_month_dirs` (comando one-shot admin, idempotente) + `audit_browse_months` **deja de renombrar en lecturas** | test `browse_is_pure_read`, `migrate_is_idempotent` |

## P2 — Lógica de guardado robusta (backend)

| # | Tarea | Criterio de verificación |
|---|---|---|
| P2.1 | `atomic_write` con `fsync`: temp → `File::sync_all()` → rename → fsync del dir padre (best-effort) | test `atomic_write_roundtrip_cleans_temp`; (fsync no es testeable por crash: se verifica por conteo de syscalls de integración manual — documentado, no invetado) |
| P2.2 | Lock por archivo-día: lockfile `O_EXCL` con timeout y detección de hold muerto (staleness por mtime/hostname). Save = read-modify-write **bajo lock** | test `concurrent_saves_do_not_lose_hours` (2 hilos + barrier, ambas horas presentes) |
| P2.3 | `schema_version` inyectado en todo JSON nuevo/actualizado (constante `SCHEMA_VERSION: i64` en `domain`, con migración futura documentada) | test `saved_json_contains_schema_version` |
| P2.4 | Retención de backups: máx 10 por archivo-día *(actual)* + `backups_max_age_days` (default 30) + cap total de bytes por estación; dedupe de copia al save si el contenido no cambió (sha256) | test `backup_rotation_respects_age_count_and_bytes`, `backup_skips_unchanged_content` |
| P2.5 | Save detallado: los errores de guardado devuelven `{ path, stage, detail }` para que la UI muestre detalle real (no toast genérico) | test `save_error_carries_stage_and_path` |

## P3 — Dual-destination + cola de sincronización (backend)

| # | Tarea | Criterio de verificación |
|---|---|---|
| P3.1 | Migración tabla `sync_pending(id, module, station_code, relative_path, source_path, target_path, sha256, attempts, last_error, created_at, synced_at)` — un solo up-migration | `cargo test` + `alembic-free` (SQL en db.rs) |
| P3.2 | `save_observation_json` (y CLIs) reciben destino dual: offline write OK → intentar online write atómico igual al offline. Falla online → fila en `sync_pending`. La respuesta del comando incluye `offline_saved: bool, online_saved: bool` | tests `online_success_writes_both_roots`, `online_failure_keeps_offline_and_enqueues` |
| P3.3 | `retry_pending_sync` (comando admin+encargado): procesa la cola con skip por sha256 si el destino ya tiene el mismo hash; marca `synced_at` al éxito; backoff por intentos; invocada al startup + cada 10 min en background + botón manual en UI | tests `retry_uploads_when_online_returns`, `retry_skips_same_sha`, `retry_backoff_respected`, `sync_state_recorded` |
| P3.4 | Estado consultable: `get_sync_status` → conteo pendiente, último intento, últimos N errores (para la UI) | test `sync_status_aggregates_queue` |
| P3.5 | Conflicto del lado destino: si existe archivo online con contenido distinto al propio y no es "propio" (estación distinta no aplica — carpetas por estación),.*(OK sufijo `-conflict-<ts>` y encolar aviso) | test `target_conflict_gets_suffixed_and_windowed` |

## P4 — UI Administración (frontend)

| # | Tarea | Criterio de verificación |
|---|---|---|
| P4.1 | `SettingsPage` real (reemplaza stub `MaintenancePage`): tarjetas por ruta (offline / online opcional / backups / resúmenes), cada una con campo + botón **Explorar** (`@tauri-apps/plugin-dialog` open directory) + botón "Probar" que llama `probe_path` y muestra OK/cartel de error real. Solo admin (RoleRoute) | vitest `settings_renders_and_probes_paths`, `settings_saves_profile`, wiring test actualizado |
| P4.2 | Panel "Sincronización": pendiente count (`get_sync_status`), botón "Reintentar ahora", badge en header del si hay pendiente | vitest `sync_panel_shows_state_and_retries` |
| P4.3 | Guardado honesto: `handleSave` muestra detalle del error en toast + inline; guarda los estados `offline_saved/online_saved` como banda por día ("Guardado local ✓ · Enviado ✓/⏳ 2 pendientes") | vitest `save_feedback_dual_state` |
| P4.4 | Protección de borrador: autoguardar draft sinóptico en cada cambio **ligado a (estación, fecha)** (como ya lo hacen los CLIs); `beforeunload` + bloqueo de navegación con datos sucios | vitest `synoptic_draft_autosaves_bound_to_station_date`, `dirty_nav_blocked` |
| P4.5 | UX corto: quitar `window.confirm` de cambio de día (toast informativo); cambiar los otros 3 confirms nativos por modales propios con foco/teclado; conservar hora activa al cambiar de día | vitest `day_change_no_native_confirm`, `active_hour_preserved` |

## P5 — Indoor de calidad / Monday de suite

| # | Tarea | Criterio de verificación |
|---|---|---|
| P5.1 | `cargo test` completo verde end-to-end + `cargo clippy -D warnings` | CI `ci.yml` backend job verde |
| P5.2 | `vitest run` completo verde + wiring test afirmando que todos los comandos nuevos (`get/set_path_config`, `probe_path`, `retry_pending_sync`, `get_sync_status`, `migrate_legacy_month_dirs`) tienen caller | CI frontend job verde |
| P5.3 | WDIO e2e funcional (smoke real, no decorativo): login → settings → set offline root a carpeta temp → guardar observación → hardware verify del archivo en la ruta configurada. Solo cuenta como pasada si corre con driver disponible; si no corre, el reporte dice **NOT RUN**, nunca "aprobado" | spec `settings-save-path.spec.js`; estado explícito en el cierre |
| P5.4 | Auditoría anti-trampa: diff del PR no puede tocar `.github/workflows` para filtrar, ni `describe.skip`/`it.skip`/`--grep` exclusions; ningún test cambiado a assert de menor exigencia sin justificación en el commit body | review manual del diff de tests |

---

## Orden de ejecución y commits

1. **P1** (root config, 6 commits cortos) — sin esto nada más tiene sentido.
2. **P2** (correctitud de guardado) — tests de concurrencia primero (RED esperado).
3. **P3** (dual-destination + cola) — la cola se testea con carpeta online provisoria en temp dir (sin red real: no структural fake de Drive).
4. **P4** (UI) — vitest first; wiring test mantiene el contrato de comandos.
5. **P5** (suite inclinada + e2e + archivo final).
Branch de feature: `rutas-guardado` desde `arca-pipeline`. Cada tarea = 1 commit Conventional con tests incluidos. `$odd/tasks/rutas-guardado-configurables.md` registra commit-id y status por tarea.

## Riesgos honestos (documentados, no escondidos)

- **fsync en NTFS**: la garantía dura depende del FS; el código pone el fsync, el test de crash real es imposible automatizarlo honestamente — queda verificación manual documentada.
- **Carpetas de Drive Desktop**: rename se ve como delete+create en el lado nube; mitigamos escribiendo con temp+rename atómico y validando que el destination sea compartible; conflicto de Drive = sufijo P3.5.
- **e2e**: depende de `tauri-driver` usable en CI; si no corre, se reporta NOT RUN — no se simula.
