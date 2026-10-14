"""Frontera PyO3 F0: oms_calc.tendencia_a replica la lógica OLD verbatim.

Casos derivados de OLD/frontend/src-tauri/src/modules/synoptic/calculations.rs
(`calcular_tendencia_a`): cada rama positiva/negativa, cero y bordes de rango.
"""

import oms_calc


def test_cero_es_4():
    assert oms_calc.tendencia_a(0.0) == "4"


def test_suba_leve():
    assert oms_calc.tendencia_a(0.3) == "0"
    assert oms_calc.tendencia_a(1.0) == "1"
    assert oms_calc.tendencia_a(1.7) == "2"
    assert oms_calc.tendencia_a(2.5) == "3"


def test_baja_leve():
    assert oms_calc.tendencia_a(-0.3) == "5"
    assert oms_calc.tendencia_a(-1.0) == "6"
    assert oms_calc.tendencia_a(-1.7) == "7"
    assert oms_calc.tendencia_a(-2.5) == "8"


def test_bordes_de_rango():
    assert oms_calc.tendencia_a(0.5) == "0"
    assert oms_calc.tendencia_a(0.6) == "1"
    assert oms_calc.tendencia_a(1.4) == "1"
    assert oms_calc.tendencia_a(1.5) == "2"
    assert oms_calc.tendencia_a(2.0) == "3"
    assert oms_calc.tendencia_a(-2.0) == "8"
