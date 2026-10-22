 > **Nota (2026-10-20):** el oráculo `OLD/` fue movido fuera del repositorio a
 > `../OLD`. Las rutas `OLD/...` que aparecen en este plan y en las notas de
 > evidencias eran correctas cuando se escribieron (registro histórico);
 > hoy se leen como `../OLD/...`.

# PRD — Migración OMS "Neo Arca": React + Tauri → PySide6 + Rust

| Campo | Valor |
|---|---|
| **Código** | NEOARCA-PRD-001 |
| **Versión** | 1.0 (2026-10-14) |
| **Estado** | Aprobado como plan de trabajo — rama `neo-arca` |
| **Stack origen** | React + Tailwind (UI) · Rust + Tauri 2.11 (backend/shell) · JSON en `Documents/ARCA` (dato) |
| **Stack destino** | PySide6 + Qt Widgets (UI + datos) · Rust vía PyO3 `oms_calc` (cálculos puros) · SQLite WAL (dato) |
| **Dueño** | Responsable OMS (dev único) |
| **Horizonte** | 5 meses (M1–M5), trabajo por fases con corte piloto |

---

## 1. Resumen ejecutivo

Se migra el OMS parte por parte, sin big-bang, a una app de escritorio 100% nativa
(Linux/Windows/Mac) con **un solo lenguaje por capa**: Python para UI + datos,
Rust para cálculos certificados. Cada fase entrega algo que compila, pasa tests y se
compara contra la app actual (oráculo) antes de avanzar. El dato migra de JSON sueltos
a SQLite transaccional con importador verificado. Nada se borra del stack viejo hasta
el corte final.

## 2. Objetivos

1. Binarios nativos por plataforma con instaladores reales (sin Node, sin webview).
2. Fuente de verdad SQLite (WAL, transacciones, constraints, migraciones versionadas).
3. Cálculos OMM ejecutados en Rust (`oms_calc`), heredando los tests actuales intactos.
4. Cero regresión funcional: cada pantalla migrada debe producir los mismos resultados
   que la actual ante las mismas entradas (estrategia oráculo, §6).
5. Empaquetado reproducible ×3 OS desde CI, con firma (Windows) y notarización (macOS).

## 3. No-objetivos (para que no se cuele alcance)

- NO se rediseña la estética (Widgets sobrio + QSS; el polish visual es proyecto aparte).
- NO hay versión web (ver §10: solo se preserva la puerta con núcleo separado).
- NO se agrega ninguna feature nueva durante la migración (feature freeze, §6.5).
- NO se tocan los datos de producción con la app nueva hasta el piloto (§F8).

## 4. Punto de partida medido (2026-10-14, rama `arca-pipeline`)

| Pieza | Medición |
|---|---|
| Backend Rust `src/` | **7.051 líneas** (lógica + comandos Tauri) |
| Tests Rust `tests/` | **1.808 líneas** (auth, paths, sync, guardado dual, grupos SYNOP, migración) |
| Frontend React `frontend/src/` | ~1,4 MB en disco; 6 features (`audit, auth, dashboard, maintenance, summary, synoptic`) + 18 suites de test |
| Shell | Tauri 2.11.3, versión app 2.2.0 |
| Dato | JSON por hora/estación/mes en `Documents/ARCA` (+ `sync_pending` en SQLite solo como cola) |
| Archivos Rust clave | `modules/synoptic/calculations.rs` (650) · `modules/synoptic/storage.rs` (502) · `audit/service.rs` (474) · `infrastructure/storage/sync_queue.rs` (458) · `adapters/sqlite_audit_repository.rs` (411) · `audit/commands.rs` (370) · `modules/auth/mod.rs` (368) · `db.rs` + `json_handler/` + `infrastructure/storage/{paths_config,write_guard}` |

## 5. Arquitectura objetivo

```
NeoArca/
├── oms_calc/                 # RUST (PyO3, abi3) — funciones PURAS, sin I/O
│   └── src/lib.rs            # ← calculations.rs tal cual + validaciones matemáticas
├── oms_core/                 # PYTHON puro — SIN importar nada de Qt
│   ├── db/                   # esquema SQLite + migraciones + repositorios
│   ├── validators/           # reglas OMM no-matemáticas (longitudes, rangos, fechas)
│   ├── sync/                 # ← sync_queue.rs portado (backoff, reintentos)
│   ├── importer/             # JSON legacy → SQLite (one-shot, verificado)
│   └── services/             # auth, estaciones, resúmenes, auditoría (lógica)
├── oms_ui/                   # PySide6 Widgets — SOLO presentación
│   ├── main_window.py, pages/ (login, dashboard, synoptic, summary, audit,
│   │                          maintenance, admin), dialogs/, models/ (QSqlTableModel…)
│   └── resources.qrc + styles.qss
├── tests/
│   ├── test_calc_boundary.py # frontera PyO3: mismos casos que los tests Rust
│   ├── test_core_*.py        # pytest núcleo
│   └── test_ui_*.py          # pytest-qt (clics/teclas reales)
└── packaging/                # Briefcase/PyInstaller por OS + CI (.github/workflows)
```

**Frontera Rust (regla de oro):** datos entran, resultados salen. `oms_calc` no toca
archivos, SQLite, red ni Qt. Todo I/O vive en Python. Excepción prohibida salvo
módulo certificado aislado (requiere enmienda de este PRD).

## 6. Estrategia a prueba de fallos (leer antes de cada fase)

### 6.1 Strangler por pantalla, nunca big-bang
Cada fase migra UNA pieza. La app vieja sigue compilando y corriendo siempre.
La app nueva crece página por página detrás de un menú que indica estado
(`✅ migrada / 🟡 en curso / ⬜ pendiente`).

### 6.2 La app actual es el oráculo
Toda fase funcional termina con **corrida oráculo**: mismas entradas en app vieja y
módulo nuevo, diff de salidas. Diff ≠ vacío → la fase no cierra. Casos semilla:
días reales ya guardados (anonimizados si hace falta), meses con correcciones,
credenciales de prueba, JSON corruptos conocidos.

### 6.3 El dato no se toca dos veces
Hasta el corte (F8), solo la app vieja escribe producción. El importador JSON→SQLite
es unidireccional y re-ejecutable (idempotente por clave `estación+fecha+hora`).
Verificación por muestreo: 100% de filas contadas, 10% comparadas campo a campo,
checksums SHA-256 por archivo origen.

### 6.4 Definition of Done por fase (todas obligatorias)
1. Compila limpio en Linux (warning = error en Rust con `-D warnings`; `ruff` limpio en Python).
2. Tests verdes: heredados (Rust) + nuevos (pytest/pytest-qt) sin `skip` salvo causa escrita.
3. Corrida oráculo con diff vacío (evidencia guardada en `Migración/evidencias/F#/`).
4. Este PRD actualizado si la fase enseñó algo (el plan aprende).
5. Commit en `neo-arca` con mensaje `neoarca(F#): ...`.

### 6.5 Feature freeze
Durante M1–M5 no entra ninguna feature nueva a ninguna de las dos apps, salvo bug
crítico de producción (se parchea en la vieja y se porta el test a la nueva).

### 6.6 Rollback por fase
Cada fase es descartable: `git revert` del rango + la app vieja intacta. El corte
final (F8) exige además rollback de datos: backup SQLite + JSON originales
conservados 90 días.

## 7. Fases parte por parte

### F0 — Cimientos (M1, semana 1–2)
- Layout del repo (§5), `oms_calc` esqueleto con **1 función real** cruzando PyO3
  (`reducir_grupo`), `maturin` en CI Linux, pytest corriendo, `ruff`+`clippy` en verde.
- **Aceptación:** `import oms_calc` funciona, 1 test de frontera verde, CI en verde.
- **Rollback:** borrar el esqueleto; la app vieja ni se entera.

### F1 — Núcleo de datos Python (M1–M2)
- Portar `db.rs` → esquema SQLite + migraciones versionadas (`yoyo`/`alembic`-lite o
  migraciones numeradas propias); repositorios Python por entidad
  (observación, resumen, auditoría, usuario, estación).
- Importador JSON→SQLite idempotente + verificación §6.3.
- Portar `paths_config` (cadena `ARCA_BASE_DIR > perfil > Documents/ARCA`) y
  `write_guard` (reemplazado por transacciones; documentar la equivalencia).
- **Aceptación:** importar una estación completa real; conteos 100%, muestreo 10% limpio.

### F2 — `oms_calc` completo (M2)
- Mover `calculations.rs` íntegro (fórmulas, reducciones, agregaciones) + validaciones
  matemáticas puras. Tests Rust existentes intactos y verdes.
- `test_calc_boundary.py`: cada caso Rust representativo repetido en la frontera.
- **Aceptación:** `cargo test` verde + frontera verde + oráculo numérico (recalcular un
  mes real: diff vacío contra la app vieja).

### F3 — Auth, roles y estaciones (M2–M3)
- Portar `modules/auth` (login, hash, sesiones) + roles (`admin, control_calidad,
  encargado, observador`) + `assigned_station` + tabla de estaciones/admin.
- UI: Login + gestión de estaciones (era `StationAdminTable`).
- **Aceptación:** matriz de permisos testeada (cada rol × cada pantalla: entra/no entra),
  oráculo contra la app vieja.

### F4 — Observación Sinóptica (M3 — la pantalla reina)
- Grilla 8 horas (pares 21 campos / impares 17), grupos capados a 5, `QValidator` +
  máscaras, autoguardado/draft, `beforeunload` equivalente (`closeEvent` con guard),
  nombre de observador recordado, pre-chequeo de horas incompletas (era `SaveConfirmModal`).
- CLI 3074/4074 y fenómenos asociados (`modules/cli`, `rowUpdate`, tests `cliFenomenos`).
- Guardado vía `oms_calc` + repositorios (transacción por hora).
- **Aceptación:** cargar un día completo real, oráculo JSON-generado diff vacío,
  suite pytest-qt con el flujo Enter→validar→guardar.

### F5 — Resumen mensual (M3–M4)
- Portar `monthly_summary` (generación, tabla 31×20 con `QTableView`, gráficos básicos,
  export Excel vía `openpyxl`), selector estación/mes/año, overlay de correcciones.
- **Aceptación:** regenerar 3 meses históricos; diff vacío contra los JSON de resumen
  existentes; Excel abre sin errores.

### F6 — Auditoría (M4)
- Portar `audit/service.rs` + `adapters/sqlite_audit_repository.rs` (ya es SQLite:
  migración casi directa), reportes, observación individual, migración de meses legacy.
- **Aceptación:** oráculo de reportes + migración legacy sobre copia (nunca original).

### F7 — Dashboard, mantenimiento y sync (M4–M5)
- Centro de operaciones por rol, mantenimiento (rutas, probe, panel sync, migración),
  `sync_queue.rs` → `QThread` con backoff `2^intentos` tope 60 min, settings.
- **Aceptación:** cola con fallo simulado reintenta con backoff correcto; UI nunca se
  congela durante sync (test con `QTest` + reloj).

### F8 — Empaquetado, piloto y corte (M5)
- `packaging/`: Briefcase (o PyInstaller) × Linux (AppImage/.deb), Windows (.msi/.exe
  **firmado**), macOS (.dmg **notarizado**). CI matriz ×3 OS construyendo `oms_calc`
  (abi3) + app. Guía de instalación por rol.
- **Piloto:** 1 estación real, 30 días, parallel run (vieja escribe, nueva lee+calcula
  en sombra). Bitácora diaria de diffs. Cero diffs críticos = corte.
- **Corte:** backup total (JSON+SQLite, 90 días), switch, anuncio, archivo de la app
  vieja en rama `legacy-arca` (ya existe como nombre; reusar).
- **Aceptación:** instaladores verificados en máquina limpia por OS + checklist firmado.

## 8. Matriz de portación (origen → destino)

| Origen (actual) | Destino (Neo Arca) | Fase |
|---|---|---|
| `modules/synoptic/calculations.rs` | `oms_calc` (íntegro) | F2 |
| `modules/synoptic/storage.rs` | `oms_core/db/repos` + `oms_ui` guardado | F1/F4 |
| `modules/cli/*`, `rowUpdate.js`, reglas CLI | `oms_core/validators` + páginas CLI | F4 |
| `monthly_summary/*` | `oms_core/services/summary` + página Resumen | F5 |
| `audit/service.rs`, `commands.rs`, `sqlite_audit_repository.rs` | `oms_core/services/audit` + páginas Auditoría | F6 |
| `modules/auth/*` | `oms_core/services/auth` + Login | F3 |
| `infrastructure/storage/sync_queue.rs` | `oms_core/sync` (QThread) + panel Sync | F7 |
| `infrastructure/storage/paths_config.rs`, `write_guard.rs` | `oms_core/db/paths` + transacciones | F1 |
| `json_handler/*` | `oms_core/importer` (solo lectura legacy) + export | F1/F5 |
| `app_config.rs` | `oms_core/config` | F1 |
| React `features/synoptic` (grilla, horas, draft, modal) | `oms_ui/pages/synoptic/*` | F4 |
| React `features/summary` | `oms_ui/pages/summary/*` | F5 |
| React `features/audit` | `oms_ui/pages/audit/*` | F6 |
| React `features/dashboard` | `oms_ui/pages/dashboard/*` | F7 |
| React `features/maintenance` + `auth` | `oms_ui/pages/maintenance/*`, login | F7/F3 |
| Tests Rust (1.808 líneas) | Intactos en `oms_calc` + réplicas de frontera | F2 |
| Tests vitest (18 suites) | Réplicas pytest/pytest-qt por pantalla migrada | F3–F7 |

## 9. Reglas OMM a preservar (checklist de oráculo, no negociable)

1. Grupos SYNOP: máximo 5 caracteres, sanitización idéntica (`sanitizeSynopGroup`).
2. Horas pares 21 campos / impares 17; `YYGG Iw`, `IIiii`, `Fecha DD/MM/AAAA` con
   validación de calendario real (bisiestos incluidos).
3. Presión/temperatura: corrección de altitud por estación (`correc_alt`, `ch`).
4. Fenómenos CLI 3074/4074 con reglas 56DL/DM/DH y limpiezas cruzadas vigentes.
5. Observador bloqueado a su estación; admin/control_calidad ven todo.
6. Meses legacy con ceros a la izquierda migran una sola vez (idempotente).
7. Backoff de sync `2^intentos` min, tope 60; cola durable ante caídas.
8. Todo error de guardado informa etapa+ruta+detalle (era `SaveErr`).

## 10. Decisiones arquitectónicas registradas (ADR resumidos)

- **ADR-01 Python+Rust vía PyO3 (no sidecar, no ctypes):** frontera pura, wheel abi3
  (1 build por OS). Reevaluar solo si la frontera supera 30 funciones.
- **ADR-02 SQLite WAL como única fuente de verdad** desde F1; JSON pasa a
  lectura-legacy + formato de intercambio/exportación.
- **ADR-03 Núcleo sin Qt (`oms_core` no importa PySide6):** preserva la puerta web
  futura (FastAPI mínimo) y permite testear lógica sin GUI.
- **ADR-04 Qt Widgets (no QML):** formularios densos > estética; QSS para sobriedad.
- **ADR-05 Briefcase como empaquetador primario**, PyInstaller como plan B si un OS
  se resiste. Firmado Windows + notarización macOS obligatorios para "profesional".
- **ADR-06 LGPL Qt vía PySide6:** enlace dinámico (wheels oficiales), aviso de uso de
  Qt en Acerca-de, oferta de fuentes Qt. Sin LTS comercial: upgrade anual de Qt
  planificado (tarea recurrente en M6+).

## 11. Riesgos y mitigaciones

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Regresión silenciosa en cálculos | M | Crítico | Tests Rust intactos + frontera + oráculo numérico (F2) |
| R2 | Divergencia de datos JSON→SQLite | M | Crítico | Importador idempotente + verificación §6.3 + piloto sombra |
| R3 | Congelamientos de UI (I/O en hilo GUI) | M | Alto | Regla: todo I/O en QThread; test anti-freeze en F7 |
| R4 | Empaquetado falla en un OS | M | Alto | Plan B PyInstaller; CI matriz desde F0 (falla temprano, no en M5) |
| R5 | Antivirus/SmartScreen bloquea .exe | A | Medio | Firma de código (presupuesto M5) + instrucciones de despliegue |
| R6 | Abandono a mitad (dev único) | M | Alto | Fases con valor propio: F1+F2 ya dejan núcleo+tests reutilizables aunque pare |
| R7 | Upgrade anual Qt sin LTS | B | Medio | ADR-06: tarea recurrente calendarizada, CI lo detecta |
| R8 | Tentación de features nuevas | A | Medio | Feature freeze §6.5; ideas van a `Migración/BACKLOG.md`, no al código |

## 12. Cronograma (meses, solapable)

| Mes | Fases | Hito verificable |
|---|---|---|
| M1 | F0, F1 | CI verde ×3; importación real verificada |
| M2 | F1(cierre), F2, F3 | Cálculos heredados + login con roles |
| M3 | F4, F5(inicio) | Día sinóptico completo con oráculo limpio |
| M4 | F5(cierre), F6, F7 | Resumen + auditoría + sync sin freezes |
| M5 | F7(cierre), F8 | Instaladores firmados + piloto 30 días + corte |

Ritmo: 1 commit revisable por unidad de trabajo, tests primero donde haya regla
observable (heredado del proyecto actual), este PRD se enmienda con lo aprendido.

## 13. Criterios de éxito del programa (no solo del código)

1. Una estación opera 30 días solo con Neo Arca sin pérdida ni called shot de dato.
2. Instalación limpia por OS en <15 min por técnico no-dev (guía + instalador).
3. Cualquier dev Python medio entiende `oms_core` en 1 día (README por paquete).
4. Reversibilidad: a 90 días del corte, todo es recuperable desde backups.

## 14. Glosario mínimo

Oráculo (app vieja como referencia) · Strangler (reemplazo pieza a pieza) ·
Frontera (límite Python↔Rust) · abi3 (una wheel por OS) · WAL (modo transaccional
SQLite) · LGPL (licencia Qt que permite código cerrado con enlace dinámico) ·
QThread (hilo Qt para no congelar UI) · QSS (estilos Qt).

### F7.5 — Endurecimiento de diseño (M5, ANTES de F8)

Enmienda v1.1 (2026-10-15, a pedido del dueño: diseño perfecto antes de
empaquetar; lo funcional impecable va en F7.5-funcional separada). Cero
cambios de lógica: solo presentación + shell. Criterio de salida: screenshots
de aceptación vistos por el dueño (login, shell expandida/colapsada,
dashboard) + suite verde.

- **Tema versionado** `oms_ui/theme.qss`: paleta (fondo gris, tarjetas
  blancas, texto pizarra), acentos por módulo (Inicio/Sinóptico azul
  `#3b82f6`, Resumen violeta `#a855f7`, Auditoría naranja `#f97316`,
  Configuración teal `#0d9488`, Seguridad gris `#64748b`), estilos base de
  inputs/botones/tablas/tabs, rojo de error, verde de éxito. Fuente:
  Jakarta Sans embebida vía `QFontDatabase` si el woff2 existe en `OLD/`,
  si no sistema sans (documentar cuál quedó).
- **LoginScreen** a pantalla completa (no diálogo): fondo oscuro, tarjeta
  centrada con lockup/título/error inline/botón con estado; Enter envía;
splash "Restaurando sesión…" con restore de token (misma semántica que
el oráculo: store en memoria, si el token murió se pide login).
- **AppShell**: rail colapsable 76px ↔ 232px (persistido en `QSettings`),
  filtrado por rol intacto vía `access.py`, usuario + Salir, `QStatusBar`
  para mensajes globales. Cero placeholders nuevos; páginas F3–F7 intactas.
- **Evidencia**: PNGs offscreen (login, shell ±colapsada, dashboard) en
  `Migración/evidencias/F7.5/` + NOTA. `run_dev.py` actualizado al nuevo flujo.
- **No-objetivos F7.5-diseño**: ni una línea de `oms_core/`/`oms_calc`,
  ninguna feature, ningún cambio de comportamiento validado por tests viejos.

## 15. Log de enmiendas

| Fecha | Versión | Cambio |
|---|---|---|
| 2026-10-14 | 1.0 | Creación del plan (rama `neo-arca`). Base: auditoría del proyecto v2.2.0. |
| 2026-10-15 | 1.1 | F7.5-diseño antes de F8 (diseño perfecto primero, funcional después); F4b absorbida. |
