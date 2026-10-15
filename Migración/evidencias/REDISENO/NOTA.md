# Evidencia REDISEÑO (round 2, skills ui-ux-pro-max + pyside6-engineer)

Pedido del dueño: el flat F7.5 "horrible" → ventana login pequeña (no
fullscreen), pantalla responsive, lo más parecido a `OLD/IMG/`.

## Skills (ambas leídas enteras antes de usar)
- `ui-ux-pro-max` (global): workflow design-system/dominios, prioridades
  accesibilidad primero, sin emoji como iconos, responsive sin scroll-x.
- `pyside6-engineer` (instalada vía npx al repo `.agents/skills/`):
  arquitectura widget, layout-first, responsive desde el inicio, oráculos
  con screenshots, QSS como capa final (no sustituto de buenos widgets).

## Estudiado (6 IMG): Login glass + botón gradiente; Panel topbar + cards
con tiles de acento; Sinóptico navy; Seguridad (tablas + pills + iconos de
acción); Resumen (panel tintado + empty-state); Auditoría (acento naranja).

## Hecho
- `theme.qss` v2: botón primario con gradiente Qt-válido, pills
  (role/ok/info/warn), paneles tintados (violet/orange/blue/teal), títulos
  de card, empty-states, tiles de acento, botón círculo, links de acento.
- `login_window.py`: ventana pequeña fija (~440px) con la tarjeta directa,
  lockup, botón gradiente, footer offline. Misma API que LoginScreen
  (tests espejo). `run_dev.py` cableado a ella.
- Dashboard: StationCard con tile de acento estable por estación +
  monograma + título + link; grid responsive (1/2/3 cols por ancho) +
  `QScrollArea` (el contenido bajo el fold era inalcanzable: gap real
  hallado por screenshot).
- Tests: 2 login-window + 1 columnas responsive; suite **362 passed**,
  ruff limpio.

## Incidentes propios (todos verificados con fix)
1. Badge tragado dentro de `_relayout_cards` (NameError) — 20 rotos → fix.
2. `QSettings` real contaminado por mis scripts de screenshots (rail=True)
   rompió el test del rail — limpieza + test hermético, probado pre-
   contaminando a propósito (11 passed).

## Puertas (locales)
- `pytest -q` (GIL, offscreen): **362 passed**.
- `ruff check oms_core oms_ui tests packaging run_dev.py`: limpio.
- Screenshots: `login_window.png`, `shell_cards.png`, `shell_narrow.png`
  (1-col probada por test; en shell el mínimo Qt la limita) — vistos y
  aprobados por el padre.
