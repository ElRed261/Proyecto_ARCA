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
