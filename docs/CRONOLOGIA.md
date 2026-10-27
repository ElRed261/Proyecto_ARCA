# Cronología del proyecto — de ARCA 2.2.0 a Neo Arca

Registro cronológico completo de todo el trabajo realizado. Cada entrada
cita su commit en la rama `neo-arca`. El detalle técnico de cada fase está
en `Migración/PLAN_MIGRACION_NEoARCA.md` (PRD) y en
`Migración/evidencias/<fase>/` (capturas + notas).

---

## Era 1 — Proyecto ARCA (React + Tauri), versión 2.2.0

La aplicación original: frontend React + backend Rust (Tauri 2.11),
datos JSON en `Documents/ARCA`, sincronización Jimaní → Santo Domingo
offline-first. Todo ese código quedó archivado en `OLD/` y es el
**oráculo** de esta reescritura (ver `docs/CONTRATO_ORACULO.md`).

| Commit | Qué |
|---|---|
| `dea0556` | Configuración real de rutas con probe de escritura (P4) |
| `dc648c3` | Página de settings admin real + salvaguardas del observador |
| `9288a4d` | Dependabot mensual agrupado (tras limpiar 103 ramas) |
| `e519f88` / `db9a986` | Release v2.2.0 |
| `10e40e1` | Pasada de consistencia visual (skill ui-ux-pro-max) |
| `da548de` | Rebrand: ARCA pasa a ser un OMS (Observations Management System) |
| `a2a1a99` | Tipografía de marca embebida + controles unificados |
| `29b87b9` | Correcciones guiadas por IMG (etiquetas canónicas, login, date field) |
| `58b62fd` | CLI 3074: fenómenos siempre seleccionables + combo moderno |
| `25bff18` | Sidebar colapsable híbrida |
| `bc6217e` / `df11717` | Dashboard como centro de operaciones + scope por rol |
| `361ffca` / `5a6aa6e` | Rail con gradiente por hora |
| `255b3df` | Lotes UX Sinóptico A+B+C: orientación, teclado, guardado honesto |
| `9bc6e6a` | Resumen mensual: scroll único |
| `3d180dc` | Fix WebKitGTK (marca negra en hover de botones redondos) |
| `2464ab4` / `016de16` / `8859bcc` | `./run.sh`, README con SVG, cap SYNOP 5 chars |

## Era 2 — Decisión de migración y PRD

| Commit | Qué |
|---|---|
| `dab4484` | **PRD NEOARCA-PRD-001**: plan de migración React+Tauri → PySide6+Rust. Fases F0–F8, matriz de portación, 8 reglas OMM, 6 ADRs, 8 riesgos, hitos M1–M5. |

Motivo: un solo lenguaje (Python) para 1 desarrollador + núcleo de
cálculo en Rust puro vía PyO3 (`#[pyfunction]`, `maturin`, `abi3`),
Qt Widgets para UI de escritorio de productividad, SQLite WAL.

## Era 3 — Fases de migración (strangler + oráculo)

| Commit | Fase | Contenido |
|---|---|---|
| `7dd63a8` | **F0** | Archivo total a `OLD/` (git mv, sin node_modules/dist/cachés) + scaffold `oms_calc`/`oms_core`/`oms_ui`/`tests`/`packaging` + CI `neoarca.yml` + `tendencia_a` verbatim |
| `588e630` | base | LICENSE raíz (CC BY-NC-SA heredado) |
| `e38b4b9` | base | **LICENSE pasa a MIT** (decisión del dueño: la CC BY-NC-SA prohibía el uso comercial y bloqueaba piloto, API y distribución); se documenta el alcance —los datos del ONAMET y el manual OMM no se relicencian— y el plan de cumplimiento de la LGPL de PySide6 |
| `537867d` | **F1** | Núcleo de datos: migraciones M1–M5 verbatim del `db.rs` del oráculo, repos, `paths.py` (cadena ARCA_BASE_DIR>perfil>Documents/ARCA), importador JSON→SQLite idempotente SHA-256; corpus real 488 obs + 63 docs con 0 mismatches |
| `29eb9c7` | base | Swap a free-threaded 3.14t + PyO3 0.29 (multihilo real; PySide6 requiere GIL → dual-venv permanente `.venv` ft / `.venv-gil` GIL) |
| `6012951` | **F2** | `oms_calc` completo: portación verbatim de `synoptic.rs`/`monthly.rs`, 26 pyfunctions (23 + 3 frontera JSON), cirugía de `correc_alt` por parámetro; oráculo 512h-Z +1220 celdas exactas |
| `998e919` + `c669791` | **F3** | Auth (bcrypt 12, sesiones 8h, `require_role`), estaciones (espejo + deactivate), matriz de acceso 4×6, `LoginDialog`/`MainWindow`/`StationsAdminPage` |
| `01c3c89` | **F4** | Página sinóptica: 17 campos base + 4 pares-hora, validación con mensajes exactos, draft estación+fecha, guardado transaccional SAVEPOINT, atajos Ctrl+S / Alt+1..8, guard de cierre |
| `b8dabe3` | chore | `run_dev.py`: login real → Sinóptico en pantalla |
| `9558832` | **F5** | Resumen mensual: `generate_month` con overlay de correcciones, Lluvia en su día, `round_half_up`, export Excel 21 headers verbatim, UI tabla 31×20 |
| `4e8317b` | **F6** | Auditoría: mappers/carga/auto-marca verbatim, wizard 4 pasos, reportes detailed/person, migración legacy rename-or-merge, matriz `audit=(admin,control_calidad)` |
| `54712eb` | **F7** | Dashboard por rol, maintenance con probe, sync con backoff verbatim `min(2^attempts,60)` + hilo `SyncWorker`, MainWindow real sin placeholders |
| `db63ff2` | **F7.5-diseño** | Theme QSS v1 + Jakarta (5 pesos) + LoginScreen fullscreen + rail 76↔232 + splash→login→shell |
| `5256b2e` | REDISEÑO | round 2 con skills: theme v2, login_window 440px, StationCard tile+monograma, grid responsive |

## Era 4 — Recreación 1:1 de las pantallas (rondas con el dueño)

| Commit | Ronda | Contenido |
|---|---|---|
| `fb824e0` | 1 | Titlebar clamp (<1080p), cards a área completa, grilla agrupada + panel calc + panel derecho + autos + Cargar JSON + diálogo CLI genérico |
| `2201cb3` | 2 | Encabezados pegados, panel Cálculos reordenado (par izq + tablero), sidebar 198–204px con scroll, rail 200, clamp maximizar→restaurar |
| `12b3db9` | 3 | Encabezados planos sin índices, sidebar sin scroll (cards compactas), labels auto-ocultos, centro de operaciones a toda la altura |
| `d7a308a` | 4 | Toasts flotantes arriba-derecha con auto-descarte, sin flecha volver, **CLI 3074 ventana real** (grilla agrupada, fenómenos WMO, VER HORA SYNOP) |
| `0b5096b` | 5 | CLIs **en la misma ventana** (stack de vistas), volver a la última hora, pestañas 3074/4074/5074, vistas reales 4074 (nubes) y 5074 (extremos/fenómenos) |
| `c3644c6` | 6 | Toast 5s + clic, IIiii solo código, gradiente por hora en CLIs, banca FENÓMENOS GR..FC, colores desaturados, 4074 según su imagen |
| `60a4a85` | 7 | Tinte de fila principal también en VISIBILIDAD/T.PRES., header T.PRES. a altura completa, chips GR/SQ visibles, columnas del 4074 alineadas a la imagen |
| `8b3b383` | 8 | Gradiente alcanza la grilla (transparencia estructural), 12Z cielo/00Z morado, headers uniformes 3074, TOTAL a toda altura, **sin botón Guardar** (autosave), 5074 según su imagen |
| `3c001fe` | 9 | Transición de cielo real por hora local (amanecer/mediodía/golden hour/dusk/noche) + identidad roja del 5074 |
| `8c82ce3` | 10 | Disciplina roja del 5074: rocío/inicio rojo, card de estación neutral |
| `e8e2319` | 11 | Áreas de detalle protagonistas (textarea 365px), rail sin "Inicio" como opción (logo provisional), toggle estilo Gemini (clic en el vacío) |
| `abde062` | 12 | Tipografía de sección estándar en los títulos, headers sin subtítulo a toda altura, mapa de rojo final (FINAL + unidades mm/°C rojas; rocío pizarra) |

## Era 5 — Infraestructura de desarrollo

| Commit | Qué |
|---|---|
| `7b482c3` | **Suite 21min → 47s**: filtro de toast con scope por página (fuga que acumulaba 10x costo), timers inyectables (`STATUS_TOAST_MS`/`AUTOSAVE_MS`), helper `_wait_timer` con QEventLoop (qtbot.waitSignal roto con PySide6 6.12 + py3.14t), `flush_draft` blindado |

## Estado actual (corte de esta cronología)

- Rama `neo-arca` con toda la migración F0–F7.5 + 12 rondas de feedback.
- Suite completa: 413 tests en ~47s. Ruff limpio.
- Pendiente: **F8** (empaquetado ×3 SO + piloto sombra 30 días + corte),
  logo definitivo del rail, ventanas dedicadas 4074/5074 completas
  (comparten el stack), decisión de PR único vs encadenados.
- El oráculo `OLD/` sigue intacto y es la fuente de verdad de fórmulas
  y comportamiento hasta el corte.
