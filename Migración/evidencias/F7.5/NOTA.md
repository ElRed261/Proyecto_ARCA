# Evidencia F7.5-diseño (2026-10-15)

Implementado INLINE por el padre: el writer de subagentes falló 3× con
"Writer repository preparation was unavailable" (harness, diagnosticado
limpio: árbol, config y disco OK). La spec cerrada existía, se ejecutó directo.

## Hecho
- `oms_ui/theme.qss` (v1) + `theme.py` (`load_fonts/load_stylesheet/apply_theme`).
  Fuente Jakarta Sans embebida (5 pesos, 132K, copiados de `OLD/`): verificada
  cargando (`fuente: Plus Jakarta Sans` en corrida offscreen).
- `oms_ui/login_screen.py`: pantalla completa oscura + tarjeta + lockup +
  error inline + estado "Procesando..."; `LoginDialog` intacto (tests F3).
- `oms_ui/main_window.py`: rail 76px (monogramas + barra de acento por módulo)
  ↔ 232px (etiquetas), toggle persistido en `QSettings`, footer email + Salir
  (señal `logout_requested`), `QStatusBar`. Constructor + `visible_pages()`
  preservados; `_on_nav` compat kept.
- `oms_ui/startup.py`: `save/clear/try_restore_session` (paridad oráculo:
  store en memoria → restarts re-loguean). `run_dev.py` al flujo
  splash → LoginScreen → shell.
- `tests/test_f75_design.py`: 9 tests (tema, fuentes, login ×2, rail toggle +
  persistencia, filtro por rol, restore válido/muerto).

## Decisiones
- **D1 glass→flat**: el blur del oráculo web no porta a Qt; tarjeta plana sobria.
- **D2 monogramas**: sin fuente de iconos, collapsed usa iniciales con acento.
- **D3 ni una línea de `oms_core/`/`oms_calc`**: solo presentación + shell.
- Bugs propios hallados por puertas: init-order `_pages`, 11 lints, desempaquetado
  NAV_ENTRIES en `visible_pages` (silenciaba la navegación).

## Puertas (locales)
- `pytest -q` (GIL, offscreen): **359 passed** (350 + 9 f75).
- `ruff check oms_core oms_ui tests packaging run_dev.py`: limpio.
- Screenshots offscreen: `login.png`, `shell_expanded.png`,
  `shell_collapsed.png`, `synoptic.png` — vistos y aprobados por el padre.

## DoD F7.5-diseño
1. Compila/lints limpios ✓ · 2. Tests verdes sin skips nuevos ✓ ·
3. Oráculo visual: 4 PNGs aprobados ✓ · 4. PRD enmendado v1.1 ✓ ·
5. Commit: este rango.
