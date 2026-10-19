# Neo Arca — OMS (Observations Management System)

Reescritura nativa multiplataforma (Linux / Windows / Mac) del sistema de
observaciones meteorológicas **Proyecto ARCA**:

**PySide6 + Qt Widgets** (UI + datos) · **Rust vía PyO3** (cálculos OMM) ·
**SQLite WAL** (dato) · un solo lenguaje de aplicación (Python).

- Plan maestro (PRD): `Migración/PLAN_MIGRACION_NEoARCA.md` — leer antes de tocar nada.
- **Cronología completa**: `docs/CRONOLOGIA.md` — todo lo hecho, fase por fase, con commits.
- **Contrato del oráculo**: `docs/CONTRATO_ORACULO.md` — cómo se valida contra `OLD/`
  (fórmulas verbatim, mensajes exactos, desviaciones firmadas).
- App anterior intacta: `OLD/` (React + Tauri 2.11, v2.2.0). Es el **oráculo**:
  a nivel de fórmulas y comportamiento, Neo Arca se guía por ella. No se borra
  hasta el corte (F8).

## Estado actual

Migración completa hasta **F7.5-diseño** (autenticación, sinóptica, resumen
mensual + Excel, auditoría, dashboard/sync, shell visual) + **12 rondas** de
recreación 1:1 de pantallas con el dueño (grilla sinóptica, panel de cálculos,
CLI 3074/4074/5074 embebidos, temas de cielo por hora, identidad de color por
módulo: 3074 azul / 4074 verde / 5074 rojo).

**Suite**: 413 tests en ~47s · ruff limpio · CI `neoarca.yml`.

**Pendiente**: F8 (empaquetado Briefcase/PyInstaller ×3 SO, piloto sombra
30 días, corte con backups), logo definitivo del rail.

## Estructura

```
oms_calc/    Rust (PyO3, abi3) — SOLO funciones puras: datos entran, resultados salen
oms_core/    Python sin Qt — SQLite, validaciones, sync, importador legacy
oms_ui/      PySide6 Widgets — SOLO presentación (páginas + vistas CLI)
tests/       pytest (núcleo) + pytest-qt (UI) + frontera PyO3
OLD/         Oráculo read-only (React + Tauri v2.2.0) + IMG/ de referencia
Migración/   PRD + evidencias por fase (capturas y notas)
docs/        CRONOLOGIA, CONTRATO_ORACULO, CHANGELOG
```

## Arranque rápido (desarrollo)

```bash
# núcleo + cálculo (venv free-threaded 3.14t)
python3 -m venv .venv && source .venv/bin/activate
pip install maturin pytest ruff
maturin develop --manifest-path oms_calc/Cargo.toml
pytest -q

# UI completa (venv GIL: PySide6 6.12 solo distribuye wheels con GIL)
python3 -m venv .venv-gil && source .venv-gil/bin/activate
pip install -e ".[dev]" && pip install PySide6 pytest-qt openpyxl bcrypt
maturin develop --manifest-path oms_calc/Cargo.toml --interpreter .venv-gil/bin/python

# correr la app
QT_QPA_PLATFORM=offscreen .venv-gil/bin/python run_dev.py   # con display: sin offscreen
```

**Por qué dos venvs**: el núcleo corre en Python 3.14 **free-threaded**
(multihilo real para sync/cálculo); PySide6 6.12 solo distribuye wheels
con GIL. Ambos comparten el mismo `oms_calc` compilado por `maturin`.

## Reglas del proyecto (resumen; el detalle vive en la PRD)

1. **Frontera Rust pura**: `oms_calc` no hace I/O, ni red, ni Qt — datos
   entran, resultados salen (JSON en la frontera Python).
2. **Portación verbatim** del oráculo para fórmulas y mensajes (ver
   `docs/CONTRATO_ORACULO.md`; las desviaciones están firmadas ahí).
3. **`OLD/` read-only** — la migración de datos legacy corre sobre copias.
4. **Tests primero** (RED→GREEN) y evidencia por fase en `Migración/evidencias/`.
5. **Commits** `neoarca(<fase>)` con el resultado medido en el cuerpo.
6. UI recreada 1:1 contra `OLD/IMG/*.png` — si la imagen y el JSX difieren,
   gana la imagen (decisión del dueño).

## Licencia

CC BY-NC-SA (heredada del proyecto original; revisar estrategia antes de F8).
