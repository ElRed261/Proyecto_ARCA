---
name: oms-linea-grafica
description: "Trigger: cambiar un color, espaciado o tipografía en OMS, un widget que se ve mal, aplicar un mockup, crear una pantalla, revisar contraste, o tocar un grid. Aplica la línea gráfica única del proyecto (tokens de theme.py, escalas fijas, gates de captura y contraste) sin inventar valores."
license: MIT
metadata:
  author: elred261
  version: "1.0"
---

# OMS · Línea gráfica

Contrato para cualquier cambio visual en `oms_ui/`.

## Activation Contract

Activala cuando el pedido toque **apariencia, color, tamaño, espaciado, tipografía, bordes,
grids, encabezados, estados o mockups**. No para lógica de datos.

## Hard Rules

1. **Un solo origen: `oms_ui/theme.py`.** Cero hex y cero `rgba()` en el resto de `oms_ui/`;
   `tests/test_sin_literales.py` lo gatea y exige las dos paletas con los mismos roles.
2. **Acento único**: `#034885` claro, `#6fb0e8` oscuro. Texto sobre acento: `sobre_acento`,
   **nunca** `banda_texto`.
3. **Estados por propiedad** (`active`, `error`, `collapsed`) + regla QSS +
   `theme.repolish()`. Nunca concatenar y recortar hojas con `str.replace`.
4. **Toda hoja con `$rol` pasa por `_qss()`.** Un token crudo hace que Qt descarte la regla
   entera en silencio. Orden: `.format()` primero, `_qss()` después.
5. **Escalas cerradas**: espaciado **4·8·12·16·24·32**; radios **3** campos, **6** botones,
   **12** tarjetas, **16** paneles; tipos **22/16/13/12/12/11**.
6. **Sin degradados ni fotos de fondo.** Relleno plano con alfa.
7. **Una sola zona de scroll por pantalla.**
8. **Cifras con `theme.data_font()`** (`tnum`), o las columnas no alinean.
9. **En un grid no cambia la forma**: filas, grupos, tramos y carriles se conservan; cambia
   el trazo.

## Decision Gates

| Situación | Acción |
|---|---|
| Falta un color | `theme.py` en **ambas** paletas + regenerar muestrario; el par debe pasar el mínimo WCAG |
| Un par de roles sirve sólo en un tema | Creá el rol (así nació `sobre_acento`) |
| Cambia cómo se ve un widget | `objectName`/propiedad + QSS, nunca literal inline |
| Un mockup difiere del código | Contrastalo contra el `_build()` real antes de copiarlo |
| Hay que verificar | Captura en los **dos temas** + píxel medido; mirar un PNG no es verificar |
| Piden reordenar o quitar filas de un grid | Parar: contradice una regla dura |

## Execution Steps

1. Buscá el rol en `docs/DISENO_OMS.md` §2. Si no existe → paso 2.
2. Editá `oms_ui/theme.py` (claro y oscuro) y corré
   `.venv-gil/bin/python tools/generar_paleta_html.py`; avisa si un par baja del mínimo.
3. Llevá el estilo al QSS con `objectName` o propiedad.
4. Envolvé las hojas con `_qss()`; ninguna cruda.
5. Gate: `pytest -q -m "not slow" > /tmp/s.log 2>&1; echo "EXIT=$?"` → `EXIT=0` y **cero**
   `Could not parse stylesheet`.
6. `.venv-gil/bin/python tools/capturar_pantallas.py` y verificá el píxel del elemento.
7. Commit con el rol y el ratio en el mensaje.

## Output Contract

Reportá roles usados, par de contraste y ratio, capturas por tema, la línea `EXIT=` real y
**qué quedó sin hacer**, nombrando el elemento concreto.

## References

- `references/recetas.md` — recetas y los defectos que ya costaron caro.
- `docs/DISENO_OMS.md` §2–§3 · `docs/diseno/paleta.html` (generado, no editar).
- `tools/generar_paleta_html.py` · `tools/capturar_pantallas.py` · `tests/test_sin_literales.py`
