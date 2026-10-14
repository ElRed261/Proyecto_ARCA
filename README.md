# Neo Arca — OMS (Observations Management System)

Reescritura nativa multiplataforma (Linux / Windows / Mac):
**PySide6 + Qt Widgets** (UI + datos) · **Rust vía PyO3** (cálculos OMM) · **SQLite WAL** (dato).

- Plan maestro (PRD): `Migración/PLAN_MIGRACION_NEoARCA.md` — leer antes de tocar nada.
- App anterior intacta: `OLD/` (React + Tauri 2.11, v2.2.0). Es el **oráculo**: toda fase
  nueva se valida contra ella con diff vacío. No se borra hasta el corte (F8).

## Estructura

```
oms_calc/    Rust (PyO3, abi3) — SOLO funciones puras: datos entran, resultados salen
oms_core/    Python sin Qt — SQLite, validaciones, sync, importador legacy
oms_ui/      PySide6 Widgets — SOLO presentación
tests/       pytest (núcleo) + pytest-qt (UI) + frontera PyO3
packaging/   Briefcase/PyInstaller por OS (F8)
```

## Arranque rápido (F0)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install maturin pytest ruff
maturin develop --manifest-path oms_calc/Cargo.toml
pytest -q
```

Frontera verificada: `oms_calc.tendencia_a(dif)` — característica `a` barométrica OMM,
lógica copiada verbatim de `OLD/frontend/src-tauri/src/modules/synoptic/calculations.rs`.
