#!/usr/bin/env python3
"""Genera el visor de la línea gráfica desde `oms_ui/theme.py`.

Uno no mantiene a mano un muestrario: lo genera de la misma paleta que usa la
app, así no hay dos verdades. Abre `docs/diseno/paleta.html` en el navegador.

    .venv-gil/bin/python tools/generar_paleta_html.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from oms_ui import theme  # noqa: E402

SALIDA = RAIZ / "docs" / "diseno" / "paleta.html"

#: Pares que tienen que leerse bien, con el mínimo WCAG que les corresponde.
#: Texto normal 4.5:1, texto grande 3:1, elementos de interfaz 3:1.
PARES = (
    ("texto", "fondo", 4.5, "Texto principal sobre el fondo"),
    ("texto", "superficie", 4.5, "Texto principal sobre tarjeta"),
    ("texto_alt", "superficie", 4.5, "Títulos sobre tarjeta"),
    ("suave", "superficie", 4.5, "Texto secundario"),
    ("suave_alt", "superficie", 4.5, "Rótulos y metadatos"),
    ("tenue", "superficie", 3.0, "Texto tenue (sólo informativo)"),
    ("sobre_acento", "acento", 4.5, "Texto sobre el acento (encabezados, botón)"),
    ("acento", "superficie", 3.0, "Acento como elemento gráfico"),
    ("acento_texto", "acento_suave", 4.5, "Texto de acento sobre tinte"),
    ("acento", "acento_suave", 3.0, "Acento sobre su tinte"),
    ("error", "superficie", 3.0, "Error como marca"),
    ("ok", "superficie", 3.0, "Correcto como marca"),
    ("banda_texto", "banda", 4.5, "Texto sobre banda oscura"),
)

GRUPOS = (
    ("Superficies", ("fondo", "superficie", "panel", "panel_alt", "borde", "borde_input")),
    ("Texto", ("texto", "texto_alt", "suave", "suave_alt", "tenue")),
    ("Acento", ("acento", "acento_hover", "acento_foco", "acento_suave",
                "acento_borde", "acento_texto", "acento_fondo", "sobre_acento",
                "acento_deshabilitado")),
    ("Estados", ("error", "error_fuerte", "error_suave", "ok", "ok_fuerte",
                 "ok_fondo", "ok_borde", "ok_texto")),
    ("Banda", ("banda", "banda_texto")),
    ("Módulos", ("violeta", "violeta_fuerte", "violeta_suave", "violeta_borde",
                 "naranja", "naranja_alt", "naranja_fuerte", "naranja_fondo",
                 "naranja_debil", "teal", "teal_borde", "teal_fondo",
                 "ambar", "ambar_fondo")),
)

TIPOGRAFIA = (
    ("Título de página", 22, 700, "Una sola vez por pantalla"),
    ("Título de sección", 16, 800, "Cabeceras de tarjeta"),
    ("Cuerpo", 13, 500, "Texto corriente"),
    ("Rótulo de campo", 12, 600, "Sobre cada campo"),
    ("Dato en tabla", 12, 500, "Cifras; siempre con tnum"),
    ("Metadato", 11, 500, "Fechas, contadores, ayudas"),
)

ESPACIADO = (4, 8, 12, 16, 24, 32)
RADIOS = ((3, "Campos y celdas"), (6, "Tarjetas internas y botones"),
          (12, "Tarjetas"), (16, "Paneles"))


def _lin(canal: int) -> float:
    c = canal / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(hexa: str) -> float:
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contraste(a: str, b: str) -> float:
    la, lb = luminancia(a), luminancia(b)
    alto, bajo = max(la, lb), min(la, lb)
    return (alto + 0.05) / (bajo + 0.05)


def _muestras(paleta: dict[str, str]) -> str:
    filas = []
    for titulo, roles in GRUPOS:
        fichas = []
        for rol in roles:
            color = paleta.get(rol)
            if not color:
                continue
            fichas.append(
                f'<div class="ficha"><div class="swatch" style="background:{color}"></div>'
                f'<div class="nombre">{rol}</div><div class="hex">{color}</div></div>'
            )
        filas.append(f'<h3>{titulo}</h3><div class="grilla">{"".join(fichas)}</div>')
    return "".join(filas)


def _contrastes(paleta: dict[str, str]) -> str:
    filas = []
    for rol_a, rol_b, minimo, uso in PARES:
        a, b = paleta.get(rol_a), paleta.get(rol_b)
        if not a or not b:
            continue
        r = contraste(a, b)
        ok = r >= minimo
        marca = "cumple" if ok else "NO cumple"
        filas.append(
            f'<tr class="{("ok" if ok else "mal")}">'
            f'<td>{uso}</td>'
            f'<td><code>{rol_a}</code> <span class="muestra" style="background:{a}"></span></td>'
            f'<td><code>{rol_b}</code> <span class="muestra" style="background:{b}"></span></td>'
            f'<td class="num">{r:.2f}:1</td>'
            f'<td class="num">{minimo}:1</td>'
            f'<td>{marca}</td></tr>'
        )
    return "".join(filas)


def _tipografia() -> str:
    return "".join(
        f'<tr><td style="font-size:{px}px;font-weight:{peso}">{nombre}</td>'
        f'<td class="num">{px} px</td><td class="num">{peso}</td><td>{uso}</td></tr>'
        for nombre, px, peso, uso in TIPOGRAFIA
    )


def _espaciado() -> str:
    return "".join(
        f'<div class="esp"><div class="barra" style="width:{n}px"></div>'
        f'<span>{n} px</span></div>'
        for n in ESPACIADO
    )


def _radios() -> str:
    return "".join(
        f'<div class="esp"><div class="caja" style="border-radius:{n}px"></div>'
        f'<span>{n} px · {uso}</span></div>'
        for n, uso in RADIOS
    )


def _botones(paleta: dict[str, str]) -> str:
    p, s, a, sa = paleta["acento"], paleta["superficie"], paleta["acento"], paleta["sobre_acento"]
    return f"""
<div class="fila">
  <button style="background:{a};color:{sa};border:none">Guardar observación</button>
  <button style="background:{s};color:{paleta['texto']};border:1px solid {paleta['borde_input']}">Cargar</button>
  <button style="background:{paleta['acento_suave']};color:{paleta['acento_texto']};border:1px solid {a}">Activo</button>
  <button style="background:{s};color:{paleta['tenue']};border:1px dashed {paleta['borde_input']}" disabled>Deshabilitado</button>
</div>
<div class="fila">
  <span class="enc" style="background:{a};color:{sa}">MiMiMjMj</span>
  <span class="enc" style="background:{a};color:{sa}">Fecha</span>
  <span class="enc" style="background:{a};color:{sa}">Observador</span>
</div>
"""


def main() -> int:
    claro, oscuro = theme.PALETTE_CLARO, theme.PALETTE_OSCURO
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>OMS · Línea gráfica</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin:0; font:14px/1.5 "Segoe UI", system-ui, sans-serif; }}
  .tema {{ padding:32px 40px; }}
  .claro {{ background:{claro['fondo']}; color:{claro['texto']}; }}
  .oscuro {{ background:{oscuro['fondo']}; color:{oscuro['texto']}; }}
  h1 {{ font-size:26px; margin:0 0 4px; font-weight:800; }}
  h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.08em;
        opacity:.65; margin:40px 0 12px; font-weight:700; }}
  h3 {{ font-size:13px; margin:22px 0 8px; font-weight:700; }}
  .baja {{ opacity:.7; margin:0 0 8px; font-size:13px; }}
  .grilla {{ display:flex; flex-wrap:wrap; gap:10px; }}
  .ficha {{ width:118px; }}
  .swatch {{ height:52px; border-radius:8px; border:1px solid rgba(127,127,127,.35); }}
  .nombre {{ font-size:11px; font-weight:700; margin-top:6px; }}
  .hex {{ font-size:11px; opacity:.7; font-family:ui-monospace, monospace; }}
  table {{ border-collapse:collapse; width:100%; max-width:900px; font-size:13px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid rgba(127,127,127,.25); }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  code {{ font-family:ui-monospace, monospace; font-size:12px; }}
  .muestra {{ display:inline-block; width:11px; height:11px; border-radius:3px;
              border:1px solid rgba(127,127,127,.5); vertical-align:-1px; }}
  tr.mal td {{ color:#dc2626; font-weight:700; }}
  .fila {{ display:flex; gap:10px; align-items:center; margin:10px 0 16px; flex-wrap:wrap; }}
  button {{ padding:9px 18px; border-radius:6px; font-weight:700; font-size:13px; }}
  .enc {{ padding:7px 12px; border-radius:3px; font-weight:800; font-size:12px; }}
  .esp {{ display:flex; align-items:center; gap:10px; margin:6px 0; font-size:12px; }}
  .barra {{ height:14px; background:currentColor; opacity:.55; border-radius:3px; }}
  .caja {{ width:70px; height:38px; border:2px solid currentColor; opacity:.7; }}
</style></head><body>

<section class="tema claro">
  <h1>OMS · Línea gráfica</h1>
  <p class="baja">Tema claro · generado desde <code>oms_ui/theme.py</code>. Si cambia la
  paleta de la app, este archivo se regenera: <code>tools/generar_paleta_html.py</code>.</p>

  <h2>Color</h2>
  {_muestras(claro)}

  <h2>Contraste (WCAG 2.2)</h2>
  <table><thead><tr><th>Uso</th><th>Color</th><th>Sobre</th>
  <th>Ratio</th><th>Mínimo</th><th></th></tr></thead>
  <tbody>{_contrastes(claro)}</tbody></table>

  <h2>Tipografía</h2>
  <table><thead><tr><th>Muestra</th><th>Tamaño</th><th>Peso</th><th>Uso</th></tr></thead>
  <tbody>{_tipografia()}</tbody></table>

  <h2>Espaciado</h2>
  {_espaciado()}

  <h2>Radios</h2>
  {_radios()}

  <h2>Componentes</h2>
  {_botones(claro)}
</section>

<section class="tema oscuro">
  <h1>OMS · Línea gráfica</h1>
  <p class="baja">Tema oscuro · misma estructura, roles equivalentes.</p>

  <h2>Color</h2>
  {_muestras(oscuro)}

  <h2>Contraste (WCAG 2.2)</h2>
  <table><thead><tr><th>Uso</th><th>Color</th><th>Sobre</th>
  <th>Ratio</th><th>Mínimo</th><th></th></tr></thead>
  <tbody>{_contrastes(oscuro)}</tbody></table>

  <h2>Componentes</h2>
  {_botones(oscuro)}
</section>
</body></html>
"""
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(html, encoding="utf-8")
    print(f"escrito {SALIDA.relative_to(RAIZ)} ({len(html) // 1024} KB)")

    fallos = []
    for nombre, paleta in (("claro", claro), ("oscuro", oscuro)):
        for rol_a, rol_b, minimo, uso in PARES:
            a, b = paleta.get(rol_a), paleta.get(rol_b)
            if a and b and contraste(a, b) < minimo:
                fallos.append(f"{nombre}: {uso} ({contraste(a, b):.2f} < {minimo})")
    if fallos:
        print("pares por debajo del mínimo:")
        for linea in fallos:
            print("  " + linea)
    else:
        print("todos los pares cumplen el mínimo WCAG")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
