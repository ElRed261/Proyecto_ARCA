"""Excel → JSON con ESQUEMA ESTÁNDAR (demo, ronda 34).

El esquema es fijo: todo documento lleva ``meta``, ``synop`` (las 8 horas con
TODAS sus claves), ``cli["3074"]`` (24 horas), ``cli["4074"]`` (24 filas) y
``cli["5074"]``. El convertidor lee el Excel entero y busca dónde está cada
dato; lo que no encuentra queda **vacío**, nunca ausente ni inventado.

Dos procesos: Proceso A lee las hojas Z (``synop`` + ``datos``); Proceso B lee
las hojas CLI. Regla del dueño: sin synop o sin metadatos no se guarda nada.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any

from openpyxl.utils import column_index_from_string, get_column_letter
from python_calamine import CalamineWorkbook

# ==========================================================================
# ESQUEMA ESTÁNDAR
# ==========================================================================

HORAS_SINOP = ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z")
HORAS_CLI = tuple(str(h) for h in range(1, 25))

GRUPOS_SINOP = (
    "YYGGiw", "IrIXHVV", "Nddff", "7wwW1W2", "8NhCLCMCH", "0CSDLDMDH",
    "1snTxTxTx", "2snTnTnTn", "3Ejjj", "56DLDMDH", "7R24R24R24R24",
    "555", "29UUU",
) + tuple(f"8NsChshs_{i}" for i in range(1, 7)) + tuple(f"9spspsp_{i}" for i in range(1, 25))

DATOS_SINOP = ("ts", "th", "pres_est", "p3", "p24", "t_max", "t_min",
               "t_max_24h", "t_min_24h", "ll", "ll_24h")

CAMPOS_3074 = ("pres_est", "pres_nmm", "pres_alti", "tend_car", "tend_dif",
               "temp_seco", "temp_humedo", "hum_ptor", "hum_tvap", "hum_hr",
               "viento_dir", "viento_vel", "visibilidad")
FENOMENOS = ("tiempo_presente", "granizo", "ventarron", "neblina", "trueno",
             "relampago", "rocio", "polvo", "calima", "niebla", "tornado")
CAMPOS_4074 = ("observador", "nubosidad", "temp_max", "temp_min",
               "na_tipo", "na_cant", "na_direc", "na_altura",
               "cb_tipo", "cb_cant", "cb_altura", "estado_suelo", "lluvia_6h")
CAMPOS_5074 = ("pres_est", "pres_nmm", "correc_alt", "correc_temp", "lect_bar",
               "term_anexo", "raf_dir", "raf_vel", "piche", "tanque_c",
               "evaporigrafo", "evaporimetros", "iniciales_obs",
               "observaciones_manuales")
CAMPOS_FENOMENO_5074 = ("hora", "raf_dir", "raf_vel", "intensidad", "fenomeno",
                        "inicio", "final", "duracion", "iniciales")
PROFUNDIDADES = ("5", "10", "15", "20", "25", "50", "100")


def documento_vacio() -> dict[str, Any]:
    """El estándar completo, con todo vacío."""
    return {
        "schema": 2,
        "meta": {"estacion": "", "fecha": "", "actualizado": ""},
        "synop": {h: {"observador": "", "datos": {k: "" for k in DATOS_SINOP},
                      "grupos": {k: "" for k in GRUPOS_SINOP}} for h in HORAS_SINOP},
        "cli": {
            "3074": {h: {**{k: "" for k in CAMPOS_3074},
                         "fenomenos": {k: "" for k in FENOMENOS}} for h in HORAS_CLI},
            "4074": {h: {**{k: "" for k in CAMPOS_4074},
                         "fenomenos": {k: "" for k in FENOMENOS}} for h in HORAS_CLI},
            "5074": {**{k: "" for k in CAMPOS_5074},
                     "subsuelo": {p: "" for p in PROFUNDIDADES},
                     "fenomenos": []},
        },
    }


# ==========================================================================
# Proceso A — hojas Z
# ==========================================================================

Z_RE = re.compile(r"^\d{4}Z$")
SINOP_LABELS = {
    "yyggiw": "YYGGiw", "irixhvv": "IrIXHVV", "nddff": "Nddff", "7www1w2": "7wwW1W2",
    "8nhclcmch": "8NhCLCMCH", "0csdldmdh": "0CSDLDMDH", "1snttt": "1snTxTxTx",
    "1sntxtxtx": "1snTxTxTx", "2sntdtdt": "2snTnTnTn", "2sntntntn": "2snTnTnTn",
    "3ejjj": "3Ejjj", "5eeeej": "5EEEjE", "5eeej": "5EEEjE",
    "5nfnfnfn": "5nFnFnFn", "56dldmdh": "56DLDMDH", "6rrrtr": "6RRRtr",
    "7r24r24r24r": "7R24R24R24R24", "7r24r24r24r24": "7R24R24R24R24",
    "555": "555", "29uuu": "29UUU",
}
DATOS_LABELS = {
    "ts": "ts", "th": "th", "presest": "pres_est", "presest.": "pres_est",
    "p3": "p3", "p24": "p24", "tmax": "t_max", "tmin": "t_min",
    "ll": "ll", "ll24": "ll_24h", "ll24h": "ll_24h",
    "tmax24": "t_max_24h", "tmin24": "t_min_24h",
}
VACIOS = {"", "9", "9 ", " 9", "0", "333", "0.0", "/", ".", "//./"}


def _norm(texto: Any) -> str:
    return re.sub(r"[\s.°º:_]+", "", str(texto or "")).lower()


def _abajo(hoja: list[list[Any]], fila: int, col: int) -> Any:
    if fila + 1 >= len(hoja):
        return ""
    siguiente = hoja[fila + 1]
    valor = siguiente[col] if col < len(siguiente) else ""
    return "" if str(valor if valor is not None else "").strip() in VACIOS else valor


def _celda(hoja: list[list[Any]], fila: int, letra: str) -> Any:
    if not letra or fila < 1 or fila > len(hoja):
        return ""
    col = column_index_from_string(letra) - 1
    celdas = hoja[fila - 1]
    valor = celdas[col] if col < len(celdas) else ""
    return "" if str(valor if valor is not None else "").strip() in VACIOS else valor


def slot_de(base: str) -> str | None:
    """``0006Z`` → ``06Z``, ``1200Z`` → ``12Z``, ``2100Z`` → ``21Z``."""
    match = re.match(r"^(\d{2})(\d{2})Z$", base)
    if not match:
        return None
    slot = f"{int(match.group(1)):02d}Z"
    return slot if slot in HORAS_SINOP else None


def read_synop(bases_y_hojas: dict[str, list[list[Any]]], doc: dict[str, Any]) -> tuple[str, str]:
    """Llena ``synop`` y ``datos``; devuelve (estación, fecha)."""
    estacion = ""
    fechas: dict[str, str] = {}
    for base, hoja in bases_y_hojas.items():
        nombre_slot = slot_de(base)
        if nombre_slot is None or len(hoja) < 5:
            continue
        slot = doc["synop"][nombre_slot]
        for i, fila in enumerate(hoja[:12]):
            if any(_norm(c) == "aaxx" for c in fila[:4]):
                for celda in fila:
                    texto = str(celda).strip().removesuffix(".0")
                    if not estacion and re.fullmatch(r"78\d{3}", texto):
                        estacion = texto
                    if base not in fechas:
                        if isinstance(celda, (datetime.date, datetime.datetime)):
                            fechas[base] = celda.strftime("%Y-%m-%d")
                        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", texto):
                            fechas[base] = texto[:10]
                break
        spsp = nubes = 0
        for i in range(4, min(len(hoja), 30)):
            for j, celda in enumerate(hoja[i][:10]):
                etiqueta = _norm(celda)
                if not etiqueta or etiqueta.isdigit() and len(etiqueta) < 3:
                    continue
                if etiqueta.startswith("9sp"):
                    spsp += 1
                    if spsp <= 24:
                        slot["grupos"][f"9spspsp_{spsp}"] = _abajo(hoja, i, j)
                elif etiqueta.startswith("8nsch"):
                    nubes += 1
                    if nubes <= 6:
                        slot["grupos"][f"8NsChshs_{nubes}"] = _abajo(hoja, i, j)
                elif etiqueta in SINOP_LABELS:
                    clave = SINOP_LABELS[etiqueta]
                    if not slot["grupos"].get(clave):
                        slot["grupos"][clave] = _abajo(hoja, i, j)
                elif etiqueta in DATOS_LABELS and len(str(celda)) < 24:
                    clave = DATOS_LABELS[etiqueta]
                    if not slot["datos"].get(clave):
                        slot["datos"][clave] = _abajo(hoja, i, j)
        # Los cálculos de la grilla inferior: etiqueta y valor separados por filas.
        for i in range(len(hoja) - 1, 20, -1):
            for j, celda in enumerate(hoja[i][:10]):
                etiqueta = _norm(celda)
                if etiqueta in DATOS_LABELS and not slot["datos"].get(DATOS_LABELS[etiqueta]):
                    for salto in (1, 2, 3):
                        valor = _celda(hoja, i + 1 + salto, get_column_letter(j + 1))
                        if str(valor).strip():
                            slot["datos"][DATOS_LABELS[etiqueta]] = valor
                            break
        if "observador" in slot and not slot["observador"]:
            for fila in hoja[:8]:
                if _norm(fila[0] if fila else "") == "observador" and len(fila) > 1:
                    slot["observador"] = str(fila[1] or "").strip()
    fecha = fechas.get("1200Z") or fechas.get("1200z") or (max(set(fechas.values()), key=list(fechas.values()).count)
                                    if fechas else "")
    return estacion, fecha


# ==========================================================================
# Proceso B — hojas CLI
# ==========================================================================

CLI_RE = re.compile(r"^(3074|4074|5074)")

MODELOS_3074 = {
    "V1": {"hora": "A", "fila1": 9,
           "cols": dict(zip(CAMPOS_3074, ("B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"))),
           "fen": dict(zip(FENOMENOS, ("O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y")))},
    "V4": {"hora": "B", "fila1": 10,
           "cols": dict(zip(CAMPOS_3074, ("C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O"))),
           "fen": dict(zip(FENOMENOS, ("P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")))},
    "V3": {"hora": "A", "fila1": 10,
           "cols": {"pres_est": "B", "pres_nmm": "F", "pres_alti": "J", "tend_car": "N",
                    "tend_dif": "O", "temp_seco": "R", "temp_humedo": "U", "hum_ptor": "X",
                    "hum_tvap": "AA", "hum_hr": "AD", "viento_dir": "AF", "viento_vel": "AH",
                    "visibilidad": "AK"},
           "fen": {"tiempo_presente": "AN", "granizo": "AP", "ventarron": "AQ", "neblina": "AR",
                   "trueno": "AS", "relampago": "AT", "rocio": "AU", "tornado": "AV", "calima": "AW"}},
}


def detectar_modelo(hoja: list[list[Any]]) -> str | None:
    for i in range(0, 10):
        if i >= len(hoja):
            break
        fila = [str(v).strip().upper() for v in hoja[i]]
        if len(fila) > 2 and fila[1].startswith("HORA LOCAL") and fila[2].startswith("PRESIÓN"):
            return "V4"
        if fila and fila[0] == "HORA LOCAL":
            if len(fila) > 1 and "PRESIÓN (MBAR)" in fila[1]:
                return "V3"
            return "V1"
    return None


def read_cli3074(hoja: list[list[Any]], doc: dict[str, Any]) -> str | None:
    modelo = detectar_modelo(hoja)
    if modelo is None:
        return None
    cfg = MODELOS_3074[modelo]
    for hora in range(1, 25):
        fila = cfg["fila1"] + hora - 1
        marca = str(_celda(hoja, fila, cfg["hora"])).strip().removesuffix(".0")
        if marca != str(hora):
            continue
        slot = doc["cli"]["3074"][str(hora)]
        for campo, letra in cfg["cols"].items():
            slot[campo] = _celda(hoja, fila, letra)
        for campo, letra in cfg["fen"].items():
            slot["fenomenos"][campo] = _celda(hoja, fila, letra)
    return modelo


def _desplazamiento_5074(hoja: list[list[Any]]) -> int:
    """La hoja 5074 puede estar corrida una columna (como el 3074 de Cabrera)."""
    for fila in hoja[:30]:
        for j, celda in enumerate(fila[:4]):
            if _norm(celda) == "horalocal":
                return j
    return 0


def read_cli5074(hoja: list[list[Any]], doc: dict[str, Any]) -> bool:
    d = _desplazamiento_5074(hoja)
    col = lambda letra: get_column_letter(column_index_from_string(letra) + d)
    slot = doc["cli"]["5074"]
    # Presiones: cuatro grupos (horas locales 2/8/14/20), filas 17/18/19.
    grupos = [col(x) for x in ("I", "N", "S", "X")]
    for i, letra in enumerate(grupos):
        if i == 0:
            slot["pres_est"] = _celda(hoja, 17, letra)
            slot["correc_alt"] = _celda(hoja, 18, letra)
            slot["pres_nmm"] = _celda(hoja, 19, letra)
    # Filas 13-19 del primer grupo: barómetro, termómetro anexo, corrección.
    slot["lect_bar"] = _celda(hoja, 14, grupos[0])
    slot["term_anexo"] = _celda(hoja, 15, grupos[0])
    slot["correc_temp"] = _celda(hoja, 16, grupos[0])
    # Subsuelo: profundidades en la fila 12, valores en las filas 13-15.
    for letra in ("AF", "AI", "AL", "AM", "AO", "AQ", "AT"):
        profundidad = str(_celda(hoja, 12, col(letra))).strip().removesuffix(".0")
        if profundidad in PROFUNDIDADES:
            slot["subsuelo"][profundidad] = _celda(hoja, 13, col(letra))
    # Piche / Tanque C / Evaporígrafo en la fila 20.
    slot["piche"] = _celda(hoja, 20, col("AF"))
    slot["tanque_c"] = _celda(hoja, 20, col("AH"))
    slot["evaporigrafo"] = _celda(hoja, 20, col("AL"))
    slot["iniciales_obs"] = _celda(hoja, 19, col("AM"))
    # Tabla de fenómenos desde la fila 26.
    for fila in range(26, min(len(hoja) + 1, 40)):
        hora = _celda(hoja, fila, col("Z"))
        minutos = _celda(hoja, fila, col("AB"))
        if not str(hora).strip() and not str(minutos).strip():
            continue
        registro = {
            "hora": _hora_junta(hora, minutos),
            "raf_dir": _celda(hoja, fila, col("AD")),
            "raf_vel": _celda(hoja, fila, col("AF")),
            "intensidad": _celda(hoja, fila, col("AH")),
            "fenomeno": _celda(hoja, fila, col("AI")),
            "inicio": _celda(hoja, fila, col("AK")),
            "final": _celda(hoja, fila, col("AM")),
            "duracion": _celda(hoja, fila, col("AP")),
            "iniciales": _celda(hoja, fila, col("AT")),
        }
        if any(str(v).strip() for v in registro.values()):
            slot["fenomenos"].append(registro)
    return True


def _hora_junta(horas: Any, minutos: Any) -> str:
    """El dueño pidió juntar hora y minutos en un solo valor."""
    h, m = str(horas).strip(), str(minutos).strip()
    if not h and not m:
        return ""
    if isinstance(horas, datetime.time):
        return horas.strftime("%H:%M")
    if re.fullmatch(r"\d{1,2}(\.0)?", h) and re.fullmatch(r"\d{1,2}(\.0)?", m or "0"):
        return f"{int(float(h)):02d}:{int(float(m or 0)):02d}"
    return f"{h} {m}".strip()


def read_cli4074(hoja: list[list[Any]], doc: dict[str, Any]) -> bool:
    """Cabecera del 4074: fila de rótulos + filas con la hora local."""
    for i in range(0, 12):
        if i >= len(hoja):
            break
        if any("NUBOSIDAD" in str(c).upper() or "NUB" in str(c).upper() for c in hoja[i]):
            pass
    for fila in range(1, min(len(hoja) + 1, 40)):
        hora = str(_celda(hoja, fila, "A")).strip().removesuffix(".0")
        if not re.fullmatch(r"\d{1,2}", hora) or not 1 <= int(hora) <= 24:
            continue
        slot = doc["cli"]["4074"][str(int(hora))]
        for campo, letra in (("nubosidad", "B"), ("temp_max", "V"), ("temp_min", "W")):
            valor = _celda(hoja, fila, letra)
            if str(valor).strip():
                slot[campo] = valor
        slot["observador"] = _celda(hoja, fila, "X")
    return True


# ==========================================================================
# Orquestación
# ==========================================================================


def parse_excel(ruta: str | Path) -> dict[str, Any]:
    ruta = Path(ruta)
    wb = CalamineWorkbook.from_path(str(ruta))
    hojas: dict[str, list[list[Any]]] = {}
    bases: dict[str, list[list[Any]]] = {}
    cli: dict[str, list[list[Any]]] = {}
    for nombre in wb.sheet_names:
        base = nombre.split(" (")[0].strip()
        contenido = wb.get_sheet_by_name(nombre).to_python()
        hojas[nombre] = contenido
        if Z_RE.match(base) and base not in bases:
            bases[base] = contenido
        match = CLI_RE.match(base)
        if match and base not in cli:
            cli[base] = contenido

    reporte: dict[str, Any] = {"archivo": ruta.name, "hojas_cli": sorted(cli)}
    if not bases:
        reporte["resultado"] = "descartado: sin hojas Z"
        return reporte

    doc = documento_vacio()
    estacion, fecha = read_synop(bases, doc)
    doc["meta"]["estacion"] = estacion
    doc["meta"]["fecha"] = fecha
    doc["meta"]["actualizado"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    reporte.update({"estacion": estacion, "fecha": fecha})

    if not estacion or not fecha:
        reporte["resultado"] = "descartado: sin estación o fecha en las hojas Z"
        return reporte

    if "3074" in cli:
        reporte["modelo_3074"] = read_cli3074(cli["3074"], doc)
    if "4074" in cli:
        reporte["leido_4074"] = read_cli4074(cli["4074"], doc)
    if "5074" in cli:
        reporte["leido_5074"] = read_cli5074(cli["5074"], doc)

    def llenos(bloque: dict) -> int:
        return sum(1 for v in bloque.values() if isinstance(v, (str, int, float)) and str(v).strip())

    reporte["resultado"] = "procesado"
    reporte["llenos"] = {
        "synop_grupos": sum(llenos(doc["synop"][h]["grupos"]) for h in HORAS_SINOP),
        "synop_datos": sum(llenos(doc["synop"][h]["datos"]) for h in HORAS_SINOP),
        "3074": sum(llenos(doc["cli"]["3074"][h]) for h in HORAS_CLI),
        "4074": sum(llenos(doc["cli"]["4074"][h]) for h in HORAS_CLI),
        "5074": llenos({k: v for k, v in doc["cli"]["5074"].items()
                        if isinstance(v, str)}),
        "5074_fenomenos": len(doc["cli"]["5074"]["fenomenos"]),
    }
    reporte["documento"] = doc
    return reporte


def guardar(reporte: dict[str, Any], destino: Path) -> Path | None:
    doc = reporte.get("documento")
    if not doc:
        return None
    meta = doc["meta"]
    carpeta = destino / meta["estacion"] / meta["fecha"][:4] / meta["fecha"][5:7]
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f'{meta["estacion"]}{meta["fecha"][8:10]}{meta["fecha"][5:7]}{meta["fecha"][:4]}.json'
    ruta.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return ruta
