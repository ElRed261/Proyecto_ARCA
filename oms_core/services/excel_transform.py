"""Excel → JSON: dos procesos independientes (demo, ronda 33).

Proceso A lee las hojas Z y arma el bloque ``synop``; Proceso B lee las hojas
CLI y arma ``cli[...]``. Cada uno detecta su propia estructura por etiqueta o
por cabecera, nunca por nombre de archivo ni por estación.

Regla del dueño: **el CLI solo se guarda si el synop se pudo armar**.

Limitación conocida de esta demo: el bloque ``datos`` (ts/th/pres_est/... de la
grilla de cálculos) todavía no se lee; se informa como pendiente.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from openpyxl.utils import column_index_from_string, get_column_letter
from python_calamine import CalamineWorkbook

# --------------------------------------------------------------------------
# Proceso A — hojas Z
# --------------------------------------------------------------------------

Z_RE = re.compile(r"^\d{4}Z$")

#: Etiqueta normalizada (sin espacios ni mayúsculas) → clave del documento.
SYNOP_LABELS: dict[str, str] = {
    "yyggiw": "YYGGiw",
    "irixhvv": "IrIXHVV",
    "nddff": "Nddff",
    "7www1w2": "7wwW1W2",
    "8nhclcmch": "8NhCLCMCH",
    "0csdldmdh": "0CSDLDMDH",
    "1snttt": "1snTxTxTx",
    "2sntdtdt": "2snTnTnTn",
    "3ejjj": "3Ejjj",
    "5eeeee": "5EEEjE",
    "5nfnfnfn": "5nFnFnFn",
    "56dldmdh": "56DLDMDH",
    "6rrrtr": "6RRRtr",
    "7r24r24r24r": "7R24R24R24R24",
    "555": "555",
    "29uuu": "29UUU",
}
#: Etiquetas de nubosidad, en orden de aparición (8NsChshs_1.._6).
CLOUD_LABELS = {"8nschshs", "8nschsshs", "8nschs hs"}
SPSP_LABEL = "9spspsps"
EMPTY_VALUES = {"", "9", "9 ", " 9", "0", "333", "0.0"}


def _norm(texto: Any) -> str:
    return re.sub(r"[\s.°º]+", "", str(texto or "")).lower()


def _valor(hoja: list[list[Any]], fila: int, col: int) -> Any:
    """El valor está en la celda inmediatamente debajo de la etiqueta."""
    if fila + 1 >= len(hoja):
        return None
    fila_siguiente = hoja[fila + 1]
    return fila_siguiente[col] if col < len(fila_siguiente) else None


def read_synop(bases: dict[str, str], hojas: dict[str, list[list[Any]]]) -> dict[str, Any]:
    """Devuelve ``{"meta": {...}, "synop": {...}}`` leído por etiqueta."""
    horas: dict[str, Any] = {}
    estacion = None
    fechas: dict[str, str] = {}
    desconocidas: set[str] = set()
    for base in ("0006Z", "1200Z", "0000Z", "0003Z", "0009Z", "1500Z", "1800Z", "2100Z"):
        nombre = bases.get(base)
        if nombre is None:
            continue
        hoja = hojas[nombre]
        if len(hoja) < 9:
            continue
        # La fila de metadatos no siempre es la 3: se busca la que dice AA XX y
        # se toman el código de estación y la fecha que están a su derecha.
        for i, fila in enumerate(hoja[:12]):
            if not any(_norm(c) == "aaxx" for c in fila[:4]):
                continue
            for celda in fila:
                texto = str(celda).strip().removesuffix(".0")
                if estacion is None and re.fullmatch(r"78\d{3}", texto):
                    estacion = texto
                if base not in fechas:
                    if isinstance(celda, (datetime.date, datetime.datetime)):
                        fechas[base] = celda.strftime("%Y-%m-%d")
                    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", texto):
                        fechas[base] = texto[:10]
            break
        grupos: dict[str, Any] = {}
        spsp = 0
        nubes = 0
        for i in range(4, min(len(hoja), 26)):
            fila = hoja[i]
            for j, celda in enumerate(fila[:8]):
                etiqueta = _norm(celda)
                if not etiqueta:
                    continue
                if etiqueta in CLOUD_LABELS:
                    nubes += 1
                    valor = _valor(hoja, i, j)
                    grupos[f"8NsChshs_{nubes}"] = "" if str(valor or "").strip() in EMPTY_VALUES else valor
                elif etiqueta.startswith("9sp"):
                    spsp += 1
                    valor = _valor(hoja, i, j)
                    grupos[f"9spspsp_{spsp}"] = "" if str(valor or "").strip() in EMPTY_VALUES else valor
                elif etiqueta in SYNOP_LABELS:
                    valor = _valor(hoja, i, j)
                    clave = SYNOP_LABELS[etiqueta]
                    if clave in grupos:
                        continue  # la primera aparición gana (Tx del día antes que la de 24 h)
                    grupos[clave] = "" if str(valor or "").strip() in EMPTY_VALUES else valor
                elif len(str(celda)) > 5:
                    desconocidas.add(str(celda).strip())
        if grupos:
            horas[base] = {"grupos": grupos, "datos": {}, "observador": ""}
    # La fecha no es igual en las ocho hojas (00Z/03Z son del día anterior y a
    # veces un turno se cierra al día siguiente): manda la de 12Z y, si falta,
    # la más repetida.
    fecha = fechas.get("1200Z") or (max(set(fechas.values()), key=list(fechas.values()).count)
                                    if fechas else "")
    return {
        "meta": {"estacion": estacion or "", "fecha": fecha or ""},
        "synop": horas,
        "etiquetas_desconocidas": sorted(desconocidas),
    }


# --------------------------------------------------------------------------
# Proceso B — hojas CLI
# --------------------------------------------------------------------------

CLI_RE = re.compile(r"^(3074|4074|5074)")

CLI3074_FIELDS = ["pres_est", "pres_nmm", "pres_alti", "tend_car", "tend_dif",
                  "temp_seco", "temp_humedo", "hum_ptor", "hum_tvap", "hum_hr",
                  "viento_dir", "viento_vel", "visibilidad"]
FENOMENOS = ["tiempo_presente", "granizo", "ventarron", "neblina", "trueno",
             "relampago", "rocio", "polvo", "calima", "niebla", "tornado"]

#: modelo → (columna de la hora, columna inicial de los campos, fila de la hora 1)
#: V1/V2 comparten columnas; V4 es V1 corrido una columna; V3 es una hoja ancha.
MODELOS: dict[str, dict[str, Any]] = {
    "V1": {"hora": "A", "fila1": 9,
           "cols": dict(zip(CLI3074_FIELDS, "BCDEFGHIJKLMN")),
           "fen": dict(zip(FENOMENOS, "OPQRSTUVWXY"))},
    "V4": {"hora": "B", "fila1": 10,
           "cols": dict(zip(CLI3074_FIELDS, "CDEFGHIJKLMNO")),
           "fen": dict(zip(FENOMENOS, "PQRSTUVWXYZ"))},
    "V3": {"hora": "A", "fila1": 10,
           "cols": {"pres_est": "B", "pres_nmm": "F", "pres_alti": "J",
                    "tend_car": "N", "tend_dif": "O", "temp_seco": "R",
                    "temp_humedo": "U", "hum_ptor": "X", "hum_tvap": "AA",
                    "hum_hr": "AD", "viento_dir": "AF", "viento_vel": "AH",
                    "visibilidad": "AK"},
           "fen": {"tiempo_presente": "AN", "granizo": "AP", "ventarron": "AQ",
                   "neblina": "AR", "trueno": "AS", "relampago": "AT",
                   "rocio": "AU", "tornado": "AV", "calima": "AW",
                   "polvo": "", "niebla": ""}},
}


def detectar_modelo(hoja: list[list[Any]]) -> str | None:
    """Detecta el modelo por cabecera: nunca por nombre de archivo ni estación."""
    for i in range(0, 10):
        if i >= len(hoja):
            break
        fila = [str(v).strip().upper() for v in hoja[i]]
        if any(v == "HORA LOCAL" for v in fila[:2]) and "ESTACIÓN" in " ".join(fila[:4]):
            return "V1"  # A = hora, B = Estación
        if len(fila) > 2 and fila[0] == "HORA LOCAL" and "PRESIÓN (MBAR)" in fila[1]:
            return "V3"
        if len(fila) > 2 and fila[1].startswith("HORA LOCAL") and fila[2].startswith("PRESIÓN"):
            return "V4"
    return None


def _celda(hoja: list[list[Any]], fila: int, letra: str) -> Any:
    if not letra or fila < 1 or fila > len(hoja):
        return None
    col = column_index_from_string(letra) - 1
    celdas = hoja[fila - 1]
    return celdas[col] if col < len(celdas) else None


def _vacio(valor: Any) -> str:
    texto = str(valor if valor is not None else "").strip()
    return "" if texto in EMPTY_VALUES or texto in {"/", "//./", "."} else texto


def read_cli3074(nombre: str, hoja: list[list[Any]]) -> tuple[dict[str, Any], str | None]:
    modelo = detectar_modelo(hoja)
    if modelo is None:
        return {}, None
    cfg = MODELOS[modelo]
    filas: dict[str, Any] = {}
    for hora in range(1, 25):
        fila = cfg["fila1"] + hora - 1
        if _vacio(_celda(hoja, fila, cfg["hora"])) not in (str(hora), f"{hora}.0"):
            continue
        registro: dict[str, Any] = {campo: _vacio(_celda(hoja, fila, letra))
                                    for campo, letra in cfg["cols"].items()}
        registro["fenomenos"] = {campo: _vacio(_celda(hoja, fila, letra))
                                 for campo, letra in cfg["fen"].items() if letra}
        registro["observador"] = ""
        filas[str(hora)] = registro
    return filas, modelo


# --------------------------------------------------------------------------
# Orquestación
# --------------------------------------------------------------------------


def parse_excel(ruta: str | Path) -> dict[str, Any]:
    ruta = Path(ruta)
    wb = CalamineWorkbook.from_path(str(ruta))
    hojas: dict[str, list[list[Any]]] = {}
    bases: dict[str, str] = {}
    cli: dict[str, str] = {}
    for nombre in wb.sheet_names:
        base = nombre.split(" (")[0].strip()
        hojas[nombre] = wb.get_sheet_by_name(nombre).to_python()
        if Z_RE.match(base) and base not in bases:
            bases[base] = nombre          # primera aparición: el nombre exacto gana
        match = CLI_RE.match(base)
        if match and base not in cli:
            cli[base] = nombre

    reporte: dict[str, Any] = {"archivo": str(ruta.name), "hojas_cli": sorted(cli)}
    if not bases:
        reporte["resultado"] = "descartado: sin hojas Z"
        return reporte

    synop = read_synop(bases, hojas)
    reporte["estacion"] = synop["meta"]["estacion"]
    reporte["fecha"] = synop["meta"]["fecha"]
    reporte["horas_synop"] = sorted(synop["synop"])
    reporte["etiquetas_desconocidas"] = synop["etiquetas_desconocidas"]

    documento: dict[str, Any] = {
        "schema": 2,
        "meta": {"estacion": synop["meta"]["estacion"], "fecha": synop["meta"]["fecha"]},
        "synop": synop["synop"],
        "cli": {},
    }
    # Regla del dueño: sin synop no se guarda CLI.
    if not synop["synop"] or not documento["meta"]["estacion"] or not documento["meta"]["fecha"]:
        reporte["resultado"] = "descartado: sin synop o sin metadatos"
        return reporte
    reporte["resultado"] = "procesado"

    for base, nombre in sorted(cli.items()):
        if base == "3074":
            filas, modelo = read_cli3074(nombre, hojas[nombre])
            reporte["modelo_3074"] = modelo
            if filas:
                documento["cli"]["3074"] = filas
            else:
                reporte.setdefault("avisos", []).append("3074 no reconocido: bloque vacío")
        else:
            reporte.setdefault("avisos", []).append(f"{base}: hoja presente, lectura pendiente")
    reporte["cli_guardados"] = sorted(documento["cli"])
    reporte["documento"] = documento
    return reporte


def guardar(reporte: dict[str, Any], destino: Path) -> Path | None:
    documento = reporte.get("documento")
    if not documento:
        return None
    meta = documento["meta"]
    carpeta = destino / meta["estacion"] / meta["fecha"][:4] / meta["fecha"][5:7]
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f'{meta["estacion"]}{meta["fecha"][8:10]}{meta["fecha"][5:7]}{meta["fecha"][:4]}.json'
    ruta.write_text(json.dumps(documento, ensure_ascii=False, indent=1), encoding="utf-8")
    return ruta
