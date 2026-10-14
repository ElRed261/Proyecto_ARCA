# Evidencia F0 — Cimientos (2026-10-14)

## Hecho
- Proyecto anterior mudado íntegro a `OLD/` (rentrack `git mv` + untracked agregados).
- Raíz nueva: `oms_calc/` (PyO3 abi3), `oms_core/`, `oms_ui/`, `tests/`, `packaging/`, CI `neoarca.yml`.
- `oms_calc.tendencia_a` (característica `a` OMM) copiada verbatim de
  `OLD/.../calculations.rs::calcular_tendencia_a`, expuesta sin `PyResult`
  (función infalible; clippy `useless_conversion` lo exigió).

## Puertas (todas verdes, local)
- `maturin develop` → wheel abi3 instalada, `tendencia_a(1.0) == "1"` ✓
- `pytest -q` → **4 passed** (frontera: cero, ramas ±, bordes de rango)
- `ruff check oms_core oms_ui tests packaging` → limpio
- `cargo clippy -- -D warnings` → limpio

## Decisiones
- **D1:** ruff acotado a código Neo Arca. `OLD/` tiene 226 violaciones legacy y es
  oráculo, no producto: no se lintea ni se toca (CI refleja el scope).
- **D2:** artefactos regenerables eliminados antes de archivar
  (`node_modules` 443M, `dist`, cachés): se regeneran con `npm ci`.
- **D3:** `Migración/` (plan) y dot-configs de harness (`.agent`, `.atl`,
  `.codebase-memory`) quedaron fuera de `OLD/` a propósito.

## DoD F0 (§6.4 PRD)
1. Compila limpio ✓ (clippy -D warnings)
2. Tests verdes ✓ (4/4, sin skips)
3. Oráculo: N/A (primera función; réplica exacta verificada por casos)
4. PRD: sin enmienda necesaria
5. Commit: este rango

## Addendum post-F1 — intérprete free-threaded (multihilo real)
- `.venv` recreado sobre CPython 3.14.7 free-threaded (`gil: False`, vía `uv`).
- `pyo3` 0.22 → 0.29 (0.22 no trae `abi3-py313`; 0.29 sí + soporte ft).
- Lección: maturin usa el intérprete equivocado si el venv no está activado
  (salió tag `cp313-abi3` en vez de `cp314-cp314t`); fijar con `-i` o `VIRTUAL_ENV`.
- Consecuencia: bajo free-threaded el wheel es **por versión** (`cp314t`),
  no abi3 universal → rebuild por versión de Python (documentado, aceptado).
- Puertas re-verificadas bajo ft: pytest 75/75, ruff limpio, clippy limpio +
  smoke de 4 hilos concurrentes contra `oms_calc` con resultados correctos.
