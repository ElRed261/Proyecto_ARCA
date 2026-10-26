"""Excel → JSON con el esquema v3 congelado.

Contrato: `docs/ESQUEMA_OBSERVACION.md` (ESQUEMA-NUEVO-v3).

Árbol de identificación (ronda del dueño):
  N0  ha de ser un Excel legible (.xlsm/.xlsx/.xls/.xltm);
  N1  ha de tener hojas Z — sin Z no se procesa (solo CLI o no-observación);
  N2  las hojas CLI se toman si existen (el nombre exacto gana sobre el
      sufijado); sin CLI los tres bloques salen vacíos pero completos;
  N3  el layout de cada hoja CLI se detecta por SU CABECERA (nunca por el
      nombre del archivo ni por la estación);
  N4  las hojas Z se leen por ETIQUETA (rótulo arriba, valor abajo).
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from python_calamine import CalamineWorkbook

SCHEMA_VERSION = "ESQUEMA-NUEVO-v3"

HORAS_SINOP = ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z")
HORAS_24 = tuple(str(h) for h in range(1, 25))
PROFUNDIDADES = ("5", "10", "15", "20", "25", "50", "100")
FENOMENOS = ("granizo", "ventarron", "neblina", "trueno", "relampago",
             "rocio", "polvo", "calima", "niebla", "tornado")
DATOS_SINOP = ("ts", "th", "pres_est", "p3", "p24", "Tmax", "Tmin",
               "Tmax_24h", "Tmin_24h", "LL", "LL_24h")
GRUPOS_BASE = ("YYGGiw", "IrIXHVV", "Nddff", "7wwW1W2", "8NhCLCMCH",
               "0CSDLDMDH", "1snTxTxTx", "2snTnTnTn", "3Ejjj", "5EEEjE",
               "5nFnFnFn", "56DLDMDH", "6RRRtr", "7R24R24R24R24",
               "555", "29UUU")

Z_RE = re.compile(r"^\d{4}Z$")
CLI_RE = re.compile(r"^(3074|4074|5074)")
VACIOS = {"", "9", "9 ", " 9", "0", "0.0", "333", "555", "/", ".", "//./", "-"}

SYNOP_LABELS = {
    "yyggiw": "YYGGiw", "irixhvv": "IrIXHVV", "nddff": "Nddff",
    "7www1w2": "7wwW1W2", "8nhclcmch": "8NhCLCMCH", "0csdldmdh": "0CSDLDMDH",
    "1snttt": "1snTxTxTx", "1sntxtxtx": "1snTxTxTx",
    "2sntdtdtd": "2snTnTnTn", "2sntdtdt": "2snTnTnTn", "2sntntntn": "2snTnTnTn",
    "3ejjj": "3Ejjj", "5eeejee": "5EEEjE", "5eeeje": "5EEEjE",
    "5nfnfnfn": "5nFnFnFn", "56dldmdh": "56DLDMDH",
    "6rrrtr": "6RRRtr", "7r24r24r24r": "7R24R24R24R24",
    "7r24r24r24r24": "7R24R24R24R24", "555": "555", "29uuu": "29UUU",
}
DATOS_LABELS = {
    "ts": "ts", "th": "th", "presest": "pres_est", "presestacion": "pres_est",
    "p3": "p3", "p24": "p24", "tmax": "Tmax", "tmin": "Tmin",
    "tmax24h": "Tmax_24h", "tmax24": "Tmax_24h",
    "tmin24h": "Tmin_24h", "tmin24": "Tmin_24h",
    "ll": "LL", "ll24h": "LL_24h", "ll24": "LL_24h",
}


def _norm(texto: Any) -> str:
    return re.sub(r"[\s.°º:_()]+", "", str(texto or "")).lower()


def _texto(valor: Any) -> str:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(int(valor)) if float(valor).is_integer() else str(valor)
    texto = str(valor if valor is not None else "").strip()
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    return texto


def _vacio(valor: Any) -> str:
    return "" if _texto(valor) in VACIOS else _texto(valor)


# ==========================================================================
# ESQUEMA V3 — el documento completo siempre
# ==========================================================================


def documento_vacio(estacion: str = "", fecha: str = "") -> dict[str, Any]:
    fen = dict(tiempo_presente="", **{k: False for k in FENOMENOS})
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {"estacion": estacion, "fecha": fecha, "actualizado": ""},
        "synop": {
            h: {"observador": "",
                "datos": {k: "" for k in DATOS_SINOP},
                "grupos": {
                    **{k: "" for k in GRUPOS_BASE},
                    **{f"8NsChshs_{i}": "" for i in range(1, 7)},
                    **{f"9spspsp_{i}": "" for i in range(1, 25)},
                }}
            for h in HORAS_SINOP
        },
        "cli": {
            "3074": {h: {"viento_vel": "", "pres_alti": "",
                         "fenomenos": dict(fen)} for h in HORAS_24},
            "4074": {h: {"observador": ""} for h in HORAS_24},
            "5074": {
                "piche": "", "tanque_c": "", "evaporigrafo": "",
                "subsuelo": {p: {"f1": "", "f2": "", "f3": ""}
                             for p in PROFUNDIDADES},
                "notas": "", "iniciales_obs": "",
                "iniciales_grupos": {h: "" for h in ("2", "8", "14", "20")},
                "fenomenos": [],
            },
        },
    }


def _debajo(hoja: list[list[Any]], fila: int, col: int) -> str:
    """El valor vive en la celda inmediatamente debajo del rótulo."""
    if fila + 1 >= len(hoja) or col >= len(hoja[fila + 1]):
        return ""
    return _vacio(hoja[fila + 1][col])


# ==========================================================================
# Proceso A — hojas Z → synop (por etiqueta)
# ==========================================================================


def _slot(base: str) -> str | None:
    m = re.match(r"^(\d{2})(\d{2})Z$", base)
    if not m:
        return None
    nombre = f"{int(m.group(1)):02d}Z"
    return nombre if nombre in HORAS_SINOP else None


def read_synop(bases: dict[str, list[list[Any]]],
               doc: dict[str, Any]) -> tuple[str, str]:
    estacion = ""
    fechas: dict[str, str] = {}
    for base, hoja in sorted(bases.items()):
        nombre_slot = _slot(base)
        if nombre_slot is None or len(hoja) < 6:
            continue
        slot = doc["synop"][nombre_slot]
        # La fila con AA XX lleva a su derecha estación y fecha (contenido).
        for fila in hoja[:12]:
            prefijo = [_norm(c) for c in (fila[:6] if len(fila) > 6 else fila)]
            if "aaxx" not in prefijo[:4]:
                continue
            for celda in fila:
                if isinstance(celda, (datetime.date, datetime.datetime)):
                    fechas.setdefault(base, celda.strftime("%Y-%m-%d"))
                elif re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", _texto(celda)):
                    fechas.setdefault(base, _texto(celda)[:10])
                elif re.fullmatch(r"78\d{3}", _texto(celda)) and not estacion:
                    estacion = _texto(celda)
            break
        spsp = nubes = 0
        vistos: set[str] = set()
        limites = min(len(hoja), 30)
        for i in range(3, limites):
            fila = hoja[i]
            ancho = min(len(fila), 12)
            for j in range(ancho):
                etiqueta = _norm(fila[j])
                if not etiqueta:
                    continue
                if etiqueta.startswith("9sp") and spsp < 24:
                    spsp += 1
                    slot["grupos"][f"9spspsp_{spsp}"] = _debajo(hoja, i, j)
                elif etiqueta.startswith("8nsch") and nubes < 6:
                    nubes += 1
                    slot["grupos"][f"8NsChshs_{nubes}"] = _debajo(hoja, i, j)
                elif etiqueta in SYNOP_LABELS and etiqueta not in vistos:
                    vistos.add(etiqueta)
                    slot["grupos"][SYNOP_LABELS[etiqueta]] = _debajo(hoja, i, j)
                elif etiqueta in DATOS_LABELS and len(str(fila[j])) < 22:
                    clave = DATOS_LABELS[etiqueta]
                    valor = _debajo(hoja, i, j)
                    if valor and not slot["datos"][clave]:
                        slot["datos"][clave] = valor
        # observador: la fila con "Observador", nombre en la misma celda o abajo
        for i, fila in enumerate(hoja[:8]):
            primero = fila[0] if fila else ""
            if _norm(primero) == "observador":
                nombre = _vacio(fila[1]) if len(fila) > 1 else ""
                slot["observador"] = nombre or _debajo(hoja, i, 0)
                break
    fecha = ""
    if fechas:
        fecha = fechas.get("1200Z") or max(
            set(fechas.values()), key=list(fechas.values()).count)
    return estacion, fecha


# ==========================================================================
# Proceso B — hojas CLI (modelo por cabecera)
# ==========================================================================


def _pos_hora_local(hoja: list[list[Any]]) -> tuple[int, int]:
    """(fila, columna 0-based) del rótulo HORA LOCAL, o (-1, -1)."""
    for i in range(0, min(len(hoja), 10)):
        for j, celda in enumerate(hoja[i][:4]):
            if _norm(celda) == "horalocal":
                return i + 1, j
    return -1, -1


def _fila_primera_hora(hoja: list[list[Any]]) -> int:
    """1-based: la fila cuyo col A contiene la hora 1; 0 si no existe."""
    for i in range(4, min(len(hoja), 30)):
        if _texto(hoja[i][0]) in ("1", "1.0"):
            return i + 1
    return 0


def detectar_modelo_3074(hoja: list[list[Any]]) -> str | None:
    fila_cap, col = _pos_hora_local(hoja)
    if fila_cap == -1:
        return None
    if col == 1:                       # HORA LOCAL en la columna B → corrida
        return "V4"
    # V1 compacta: primera hora en la fila 9. V3 ancha (dígitos sueltos): en la 10.
    primera = _fila_primera_hora(hoja)
    if primera == 9:
        return "V1"
    if primera == 10:
        return "V3"
    return None


def _letra(hoja: list[list[Any]], fila1: int, letra: str) -> Any:
    """Celda 1-based por letra de columna, tolerante a filas cortas."""
    from openpyxl.utils import column_index_from_string
    col = column_index_from_string(letra) - 1
    if 1 <= fila1 <= len(hoja) and col < len(hoja[fila1 - 1]):
        return hoja[fila1 - 1][col]
    return ""


FEN_COLS = dict(granizo="P", ventarron="Q", neblina="R", trueno="S",
                relampago="T", rocio="U", polvo="V", calima="W",
                niebla="X", tornado="Y")
FEN_COLS_V4 = dict(granizo="Q", ventarron="R", neblina="S", trueno="T",
                   relampago="U", rocio="V", polvo="W", calima="X",
                   niebla="Y", tornado="Z")


def read_cli3074(hoja: list[list[Any]], doc: dict[str, Any],
                 modelo: str) -> None:
    if modelo == "V4":
        filas, col_hora, fen_cols = 10, 1, FEN_COLS_V4
        cols = {"viento_vel": "M", "pres_alti": "N", "hay_tp": "P"}
    else:                              # V1 (y V2, mismo layout)
        if modelo != "V1":
            return
        filas, col_hora, fen_cols = 9, 0, FEN_COLS
        cols = {"viento_vel": "L", "pres_alti": "M", "hay_tp": "O"}
    for hora in range(1, 25):
        fila = filas + hora - 1
        if fila > len(hoja):
            break
        marca = _texto(_letra(hoja, fila, "A" if col_hora == 0 else "B"))
        if marca not in (str(hora), f"{hora}.0"):
            continue
        slot = doc["cli"]["3074"][str(hora)]
        slot["viento_vel"] = _vacio(_letra(hoja, fila, cols["viento_vel"]))
        slot["pres_alti"] = _vacio(_letra(hoja, fila, cols["pres_alti"]))
        slot["fenomenos"]["tiempo_presente"] = _vacio(
            _letra(hoja, fila, cols["hay_tp"]))
        for feno, letra in fen_cols.items():
            valor = _texto(_letra(hoja, fila, letra))
            slot["fenomenos"][feno] = valor in ("1", "1.0", "SI", "si", "Sí")


def read_cli4074(hoja: list[list[Any]], doc: dict[str, Any]) -> None:
    """4074 del esquema: solo las iniciales del observador por hora."""
    for fila in range(1, min(len(hoja) + 1, 40)):
        marca = _texto(_letra(hoja, fila, "A"))
        if not re.fullmatch(r"\d{1,2}(\.0)?", marca):
            continue
        hora = int(float(marca))
        if not 1 <= hora <= 24:
            continue
        doc["cli"]["4074"][str(hora)]["observador"] = _vacio(
            _letra(hoja, fila, "X"))


def _hora_junta(horas: Any, minutos: Any) -> str:
    h, m = _texto(horas), _texto(minutos)
    if isinstance(horas, datetime.time):
        return horas.strftime("%H:%M")
    if not h and not m:
        return ""
    if re.fullmatch(r"\d{1,2}(\.0)?", h) and re.fullmatch(r"\d{1,2}(\.0)?", m or "0"):
        return f"{int(float(h)):02d}:{int(float(m or 0)):02d}"
    return f"{h} {m}".strip()


def _letra_des(hoja: list[list[Any]], fila1: int, des: int, letra: str) -> Any:
    from openpyxl.utils import column_index_from_string, get_column_letter
    destino = column_index_from_string(letra) + des
    return _letra(hoja, fila1, get_column_letter(destino))


def read_cli5074(hoja: list[list[Any]], doc: dict[str, Any]) -> None:
    des = _pos_hora_local(hoja)[1]     # 0 en Central, 1 en las corridas
    slot = doc["cli"]["5074"]

    # piche / tanque C / evaporígrafo: rótulos fila 18, valores fila 20
    slot["piche"] = _vacio(_letra_des(hoja, 20, des, "AF"))
    slot["tanque_c"] = _vacio(_letra_des(hoja, 20, des, "AH"))
    slot["evaporigrafo"] = _vacio(_letra_des(hoja, 20, des, "AL"))

    # subsuelo: profundidades fila 12, valores filas 13/14/15
    for letra in ("AF", "AI", "AL", "AM", "AO", "AQ", "AT"):
        prof = _texto(_letra_des(hoja, 12, des, letra))
        if prof in PROFUNDIDADES:
            slot["subsuelo"][prof] = {
                "f1": _vacio(_letra_des(hoja, 13, des, letra)),
                "f2": _vacio(_letra_des(hoja, 14, des, letra)),
                "f3": _vacio(_letra_des(hoja, 15, des, letra)),
            }

    # iniciales: grandes (AM19 aprox) y por grupo (fila 18, cols I/N/S/X)
    slot["iniciales_obs"] = _vacio(_letra_des(hoja, 19, des, "AM"))
    for hora, letra in zip(("2", "8", "14", "20"), ("I", "N", "S", "X")):
        slot["iniciales_grupos"][hora] = _vacio(_letra_des(hoja, 18, des, letra))

    # notas: el bloque de texto bajo la fila 22 (columnas B..Y)
    textos = []
    for fila in hoja[21:35]:
        for celda in fila[:25]:
            valor = _texto(celda)
            if valor and len(valor) > 2 and not valor.replace(".", "").isdigit():
                textos.append(valor)
    slot["notas"] = " ".join(textos).strip()

    # fenómenos: lista escalable desde la fila 26
    for fila in range(26, min(len(hoja) + 1, 42)):
        registro = {
            "hora": _hora_junta(_letra_des(hoja, fila, des, "Z"),
                                _letra_des(hoja, fila, des, "AB")),
            "raf_dir": _vacio(_letra_des(hoja, fila, des, "AD")),
            "raf_vel": _vacio(_letra_des(hoja, fila, des, "AF")),
            "intensidad": _vacio(_letra_des(hoja, fila, des, "AH")),
            "fenomeno": _vacio(_letra_des(hoja, fila, des, "AI")),
            "inicio": _hora_junta(_letra_des(hoja, fila, des, "AK"), ""),
            "final": _hora_junta(_letra_des(hoja, fila, des, "AM"), ""),
            "duracion": _vacio(_letra_des(hoja, fila, des, "AP")),
            "iniciales": _vacio(_letra_des(hoja, fila, des, "AT")),
        }
        if any(registro.values()):
            slot["fenomenos"].append(registro)


def _cuenta_datos(hoja: list[list[Any]], desde: int) -> int:
    """Celdas con dato en el bloque de 24 filas de hora."""
    total = 0
    for fila in hoja[desde - 1: desde + 23]:
        total += sum(1 for c in fila if _texto(c) not in ("", "0.0", "0")
                     and str(c).strip())
    return total


def _elegir(cli: dict[str, list[list[Any]]], base: str, detector) -> tuple[Any, Any]:
    """Libros con `3074` Y `3074(1)`: el nombre exacto no siempre es el bueno.

    Gana la hoja candidata con más celdas con dato en su rejilla de horas; en
    empate, el nombre exacto."""
    candidatas: list[tuple[str, list[list[Any]]]] = []
    for nombre, filas in cli.items():
        if nombre.split("(")[0].strip() == base:
            candidatas.append((nombre, filas))
    if len(candidatas) == 1:
        return candidatas[0][1], detector(candidatas[0][1])
    mejor = max(enumerate(candidatas),
                key=lambda par: (_cuenta_datos(par[1][1], 9), -par[0]),
                default=(0, (None, None)))
    hoja = mejor[1][1]
    return hoja, detector(hoja)


# ==========================================================================
# Orquestación — el árbol de identificación
# ==========================================================================


def analizar(ruta: str | Path) -> dict[str, Any]:
    rep: dict[str, Any] = {"archivo": Path(ruta).name, "ruta": str(ruta)}
    if Path(ruta).suffix.lower() not in (".xlsm", ".xlsx", ".xls", ".xltm"):
        rep["resultado"] = "descartado: no es un Excel"
        return rep
    try:
        wb = CalamineWorkbook.from_path(str(ruta))
        contenido = {n: wb.get_sheet_by_name(n).to_python()
                     for n in wb.sheet_names}
    except Exception as exc:
        rep["resultado"] = f"descartado: ilegible ({type(exc).__name__})"
        return rep

    rep["hojas"] = wb.sheet_names
    bases: dict[str, list[list[Any]]] = {}
    cli: dict[str, list[list[Any]]] = {}
    duplicadas: list[str] = []
    for nombre, filas in contenido.items():
        base = nombre.split("(")[0].strip()
        if Z_RE.match(base):
            if base in bases:
                duplicadas.append(nombre)
            else:
                bases[base] = filas
        m = CLI_RE.match(base)
        if m and base not in cli:
            cli[base] = filas
    rep["hojas_z"] = sorted(bases)
    rep["hojas_cli"] = sorted(cli)
    rep["hojas_duplicadas"] = duplicadas or None

    if not bases:                     # N1: la condición es tener hojas Z
        rep["resultado"] = ("descartado: solo CLI, no es una observación" if cli
                            else "descartado: no es una observación")
        return rep

    doc = documento_vacio()
    estacion, fecha = read_synop(bases, doc)
    rep["estacion"] = estacion
    rep["fecha"] = fecha
    if not estacion or not fecha:
        rep["resultado"] = "descartado: sin estación o fecha legible"
        return rep
    doc["meta"]["estacion"] = estacion
    doc["meta"]["fecha"] = fecha
    doc["meta"]["actualizado"] = datetime.datetime.now().astimezone(
        ).isoformat(timespec="seconds")

    if cli.get("3074"):
        hoja, modelo = _elegir(cli, "3074", detectar_modelo_3074)
        rep["modelo_3074"] = modelo if modelo else "n.a."
        if hoja is not None and modelo:
            read_cli3074(hoja, doc, modelo)
    hoja = _elegir(cli, "4074", lambda h: None)[0]
    if hoja is not None:
        read_cli4074(hoja, doc)
    hoja = _elegir(cli, "5074", lambda h: None)[0]
    if hoja is not None:
        read_cli5074(hoja, doc)

    rep["resultado"] = "procesado"
    rep["documento"] = doc
    return rep


def contenido(doc: dict[str, Any]) -> dict[str, int]:
    def llenos(bloque: Any) -> int:
        total = 0
        if isinstance(bloque, dict):
            for v in bloque.values():
                total += llenos(v)
        elif isinstance(bloque, list):
            total += len(bloque)
        elif bloque is True:
            total += 1
        elif bloque not in ("", None, False):
            total += 1
        return total

    return {
        "synop": llenos(doc["synop"]),
        "3074": llenos(doc["cli"]["3074"]),
        "4074": llenos(doc["cli"]["4074"]),
        "5074": llenos(doc["cli"]["5074"]),
    }


def escribir(reporte: dict[str, Any], destino: Path) -> Path | None:
    doc = reporte.get("documento")
    if not doc or not doc["meta"]["estacion"] or not doc["meta"]["fecha"]:
        return None
    fecha = doc["meta"]["fecha"]
    carpeta = destino / doc["meta"]["estacion"] / fecha[:4] / fecha[5:7]
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / (doc["meta"]["estacion"] + fecha[8:10] + fecha[5:7]
                      + fecha[:4] + ".json")
    ruta.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return ruta


# ==========================================================================
# Conversión por carpeta (submódulo admin)
# ==========================================================================


def ruta_destino(doc: dict[str, Any], destino_root: Path) -> Path | None:
    """El path donde escribiría ``escribir()`` sin escribir."""
    fecha = doc["meta"]["fecha"]
    if not doc["meta"]["estacion"] or not fecha:
        return None
    nombre = (doc["meta"]["estacion"] + fecha[8:10] + fecha[5:7] + fecha[:4]
              + ".json")
    return destino_root / doc["meta"]["estacion"] / fecha[:4] / fecha[5:7] / nombre


def convertir_carpeta(carpeta: str | Path, destino_root: str | Path,
                      *, sobrescribir: bool = False) -> dict[str, Any]:
    """Convierte los Excel de ``carpeta`` a documentos v3 en ``destino_root``.

    Recorre ``*.xlsm/.xlsx/.xls/.xltm`` recursivamente (las copias
    ``.pdf``/``.txt`` se ignoran de raíz), aplica el árbol de identificación a
    cada uno y escribe en ``{destino_root}/synop/<estación>/<año>/<mes>/``.

    Sin ``sobrescribir``, un día que ya existe se reporta como ``ya_existía``
    y no se toca (nunca se reemplaza a ciegas). Un archivo malo nunca lanza:
    su fila del reporte lleva el motivo.
    """
    carpeta = Path(carpeta)
    resumen = {"procesados": 0, "sin_cli_yaml": 0, "descartados": 0,
               "ya_existia": 0, "total": 0}
    del resumen["sin_cli_yaml"]
    resumen["sin_cli"] = 0
    sin_cli = 0
    filas: list[dict[str, Any]] = []
    if not carpeta.is_dir():
        resumen["error"] = f"la carpeta no existe: {carpeta}"
        return {"resumen": resumen, "filas": filas}
    extensiones = {".xlsm", ".xlsx", ".xls", ".xltm"}
    candidatos = sorted(ruta for ruta in carpeta.rglob("*")
                        if ruta.is_file() and ruta.suffix.lower() in extensiones)
    resumen["total"] = len(candidatos)
    destino_root = Path(destino_root)
    for ruta in candidatos:
        rep = analizar(ruta)
        doc = rep.get("documento")
        fila = {
            "archivo": ruta.name,
            "resultado": rep["resultado"],
            "estacion": rep.get("estacion") or "",
            "fecha": rep.get("fecha") or "",
            "modelo": rep.get("modelo_3074") or ("—" if rep.get("documento")
                                                 and not rep.get("modelo_3074")
                                                 else ""),
            "json": "",
        }
        if not doc:
            resumen["descartados"] += 1
            filas.append(fila)
            continue
        objetivo = ruta_destino(doc, destino_root)
        if objetivo is not None and objetivo.exists() and not sobrescribir:
            fila["resultado"] = "ya_existía: no se tocó"
            fila["json"] = str(objetivo)
            resumen["ya_existia"] += 1
            filas.append(fila)
            continue
        bloque = len(_bloques_cli_vacios(doc))
        if not bloque:
            sin_cli += 1
        escribir(rep, destino_root)
        fila["json"] = str(objetivo or "")
        resumen["procesados"] += 1
        filas.append(fila)
    resumen["sin_cli"] = sin_cli
    return {"resumen": resumen, "filas": filas}


def _bloques_cli_vacios(doc: dict[str, Any]) -> list[str]:
    """Los bloques CLI que quedaron vacíos (advertencia del reporte)."""
    def lleno(bloque: Any) -> bool:
        if isinstance(bloque, dict):
            return any(lleno(v) for v in bloque.values())
        if isinstance(bloque, list):
            return len(bloque) > 0
        return bloque is True or bloque not in ("", None, False)
    return [k for k, v in doc["cli"].items() if not lleno(v)]
