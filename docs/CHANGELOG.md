# CHANGELOG — Neo Arca (rama `neo-arca`)

Formato libre por fases; el detalle completo con commits está en
`docs/CRONOLOGIA.md`.

## [0.x-migración] — en desarrollo (no release)

### Fases estructurales (strangler sobre el oráculo `OLD/`)
- **F0** Archivo total del legado en `OLD/` + scaffold PySide6/Rust/SQLite
  + CI + primera fórmula verbatim (`tendencia_a`).
- **F1** Núcleo de datos: migraciones M1–M5 verbatim del `db.rs` original,
  repos, cadena de rutas configurables, importador JSON→SQLite idempotente
  (SHA-256). Corpus real: 0 mismatches.
- **F2** `oms_calc` completo: 26 funciones PyO3 portadas verbatim
  (sinópticos + mensuales) + frontera JSON pura. Oráculo 512h: exacto.
- **F3** Auth (bcrypt/sesiones 8h/roles), estaciones, matriz 4×6, primer UI.
- **F4** Página sinóptica transaccional (SAVEPOINT), draft, atajos, guard.
- **F5** Resumen mensual + Excel export 21 headers verbatim + overlay.
- **F6** Auditoría: wizard 4 pasos, migración legacy rename-or-merge.
- **F7** Dashboard por rol, maintenance, sync con backoff + hilo worker.
- **F7.5** Shell visual: theme, Jakarta, login, rail colapsable, splash.

### Rondas de recreación 1:1 (feedback del dueño, 12 rondas)
- Rondas 1–3: grilla sinóptica agrupada, panel de cálculos (tablero),
  anchos equilibrados, clamp de maximizar→restaurar, sidebar compacta.
- Rondas 4–5: toasts flotantes, CLI 3074 real y CLIs embebidos en la misma
  ventana (back a última hora, pestañas, VER HORA SYNOP).
- Rondas 6–8: toasts 5s/clic, IIiii solo código, gradiente por hora en CLIs,
  banca FENÓMENOS corregida, 4074/5074 según sus imágenes, autosave sin
  botón Guardar.
- Rondas 9–12: transición de cielo real por hora local, identidades de
  color (3074 azul/4074 verde/5074 rojo), rail con logo (sin Inicio como
  opción), toggle estilo Gemini, tipografía de sección estándar.

### Infraestructura
- Dual-venv: núcleo free-threaded 3.14t (multihilo real) / UI GIL.
- **Suite 21min → 47s** (fix de fuga de event filter + timers inyectables
  + helper QEventLoop; `qtbot.waitSignal` roto con PySide6 6.12/py3.14t).
- RTK instalado para compresión de salidas del agente (infra local).
- CI `neoarca.yml`; dependabot mensual agrupado.

## Legado (proyecto ARCA clásico)
Ver **`../OLD`** (fuera del repositorio) — release final **v2.2.0**
(React + Tauri). El código completo es el oráculo.
