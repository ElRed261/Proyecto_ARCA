"""The single mapping table: day document <-> form fields.

Every value in an observation day is either **observed** (the operator types
it, so it is persisted) or **derived** (recomputed from observed values on
read, never stored). This module is the one place that says which is which,
so the reader and the writer can never disagree again.

See ``docs/ARQUITECTURA_DATOS.md`` for the rules (R1-R4) and the formulas.
"""

from __future__ import annotations

import re
from typing import Any

#: Document keys that are stored under ``horas[hora]["datos"]`` and the form
#: key each one feeds. ``viento_dir``/``viento_vel`` are NOT here: the
#: direction comes from the Nddff group and the speed is typed in the CLI;
#: ``correc_alt`` comes from the station's ``ch`` and ``visibilidad`` from
#: IrIXHVV, so both are derived.
OBSERVED_DATOS: tuple[tuple[str, str], ...] = (
    ("ts", "ts"),
    ("th", "th"),
    ("pres_est", "pres_est"),
    ("p3", "p3"),
    ("p24", "p24"),
    ("t_max", "Tmax"),
    ("t_min", "Tmin"),
    ("t_max_24h", "Tmax_24h"),
    ("t_min_24h", "Tmin_24h"),
    ("ll", "LL"),
    ("ll_24h", "LL_24h"),
)

#: Form keys that look like ``datos`` but are derived or typed elsewhere.
DERIVED_DATOS: tuple[str, ...] = (
    "correc_alt",   # station.ch
    "visibilidad",  # last two digits of IrIXHVV through the 75-row table
    "viento_dir",   # Nddff digits 2-3 (dd) x 10
    "viento_vel",   # typed manually in CLI 3074
)

#: The 44 SYNOP group fields the form exposes, paired with the exact name the
#: document stores. Row 14 is included: its seven lanes (9spspsp_13.._19) were
#: missing from the legacy list, which silently dropped them on load.
SYNOP_FIELDS: tuple[tuple[str, str], ...] = (
    ("meteo_2_1", "YYGGiw"),
    ("meteo_4_irixhvv", "IrIXHVV"),
    ("meteo_4_1", "Nddff"),
    ("meteo_4_6", "7wwW1W2"),
    ("meteo_6_0", "8NhCLCMCH"),
    ("meteo_6_2", "0CSDLDMDH"),
    ("meteo_6_3", "1snTxTxTx"),
    ("meteo_6_4", "2snTnTnTn"),
    ("meteo_6_5", "3Ejjj"),
    ("meteo_6_6", "5EEEjE"),
    ("meteo_8_0", "5nFnFnFn"),
    ("meteo_8_1", "56DLDMDH"),
    ("meteo_8_3", "6RRRtr"),
    ("meteo_8_4", "7R24R24R24R24"),
    ("meteo_8_5", "8NsChshs_1"),
    ("meteo_8_6", "8NsChshs_2"),
    ("extra_8ns_1", "8NsChshs_3"),
    ("extra_8ns_2", "8NsChshs_4"),
    ("meteo_10_0", "8NsChshs_5"),
    ("meteo_10_1", "8NsChshs_6"),
    ("meteo_10_2", "9spspsp_1"),
    ("meteo_10_3", "9spspsp_2"),
    ("meteo_10_4", "9spspsp_3"),
    ("meteo_10_5", "9spspsp_4"),
    ("meteo_10_6", "9spspsp_5"),
    ("meteo_12_0", "9spspsp_6"),
    ("meteo_12_1", "9spspsp_7"),
    ("meteo_12_2", "9spspsp_8"),
    ("meteo_12_3", "9spspsp_9"),
    ("meteo_12_4", "9spspsp_10"),
    ("meteo_12_5", "9spspsp_11"),
    ("meteo_12_6", "9spspsp_12"),
    ("meteo_14_0", "9spspsp_13"),
    ("meteo_14_1", "9spspsp_14"),
    ("meteo_14_2", "9spspsp_15"),
    ("meteo_14_3", "9spspsp_16"),
    ("meteo_14_4", "9spspsp_17"),
    ("meteo_14_5", "9spspsp_18"),
    ("meteo_14_6", "9spspsp_19"),
    ("meteo_16_0", "9spspsp_20"),
    ("meteo_16_1", "9spspsp_21"),
    ("meteo_16_2", "9spspsp_22"),
    ("meteo_16_3", "9spspsp_23"),
    ("meteo_16_4", "9spspsp_24"),
)

#: What each CLI persists. Everything else in those tables is derived from
#: the synoptic hour (see the architecture document, section 4).
OBSERVED_CLI3074: tuple[str, ...] = (
    "viento_vel", "pres_alti", "observador", "fenomenos"
)
OBSERVED_CLI4074: tuple[str, ...] = ("observador", "fenomenos")

#: 9Sp lanes that the legacy files polluted with the ``555`` marker, the
#: ``29uuu`` group and old UI labels. They are discarded on read.
POLLUTED_9SP_LANES = tuple(f"9spspsp_{i}" for i in range(18, 25))

#: Legacy documents spell the group with spaces; the owner asked for the
#: joined form in the new schema, so readers accept both.
_SYNOP_ALIASES = {"0CSDL DM DH": "0CSDLDMDH"}

#: A SYNOP group is at most five characters of digits and ``/``.
_GROUP_RE = re.compile(r"^[0-9/]{1,5}$")

_FORM_TO_DOC = dict(OBSERVED_DATOS)
_DOC_TO_FORM = {doc_key: form_key for form_key, doc_key in OBSERVED_DATOS}
_FORM_TO_SYNOP = dict(SYNOP_FIELDS)
_SYNOP_TO_FORM = {synop: form for form, synop in SYNOP_FIELDS}


def datos_to_document(hour_data: dict[str, Any]) -> dict[str, str]:
    """Observed form values -> ``datos`` block (only non-empty ones)."""
    out: dict[str, str] = {}
    for form_key, doc_key in OBSERVED_DATOS:
        value = hour_data.get(form_key)
        if value is None or value == "":
            continue
        out[doc_key] = str(value)
    return out


def document_to_datos(datos: dict[str, Any]) -> dict[str, str]:
    """``datos`` block -> form keys, tolerating the legacy capitalisation."""
    out: dict[str, str] = {}
    for doc_key, value in (datos or {}).items():
        form_key = _DOC_TO_FORM.get(doc_key)
        if form_key is None or value is None or str(value) == "":
            continue  # the legacy writer stored empty strings; they are no value
        out[form_key] = str(value)
    return out


def groups_to_document(hour_data: dict[str, Any]) -> dict[str, str]:
    """Observed group fields -> ``grupos`` block, dropping junk values."""
    out: dict[str, str] = {}
    for form_key, synop_name in SYNOP_FIELDS:
        value = hour_data.get(form_key)
        if value is None:
            continue
        text = str(value).strip()
        if not text or not is_group_value(text):
            continue
        out[synop_name] = text
    return out


def document_to_groups(
    grupos: dict[str, Any], *, legacy: bool = True
) -> dict[str, str]:
    """``grupos`` block -> form keys, discarding the legacy pollution.

    In the legacy (schema 1) files lanes 18..24 carry the ``555`` marker, the
    ``29uuu`` group and UI labels instead of group codes, so they are skipped
    for those documents. A schema 2 document owns all 24 lanes for real.
    """
    out: dict[str, str] = {}
    for synop_name, value in (grupos or {}).items():
        canonical = _SYNOP_ALIASES.get(synop_name, synop_name)
        if legacy and canonical in POLLUTED_9SP_LANES:
            continue
        form_key = _SYNOP_TO_FORM.get(canonical)
        if form_key is None or value is None:
            continue
        text = str(value).strip()
        if not text or not is_group_value(text):
            continue
        out[form_key] = text
    return out


def is_group_value(value: object) -> bool:
    """True when ``value`` can be stored as a SYNOP group (max 5, digits, /)."""
    text = str(value or "").strip()
    return bool(_GROUP_RE.match(text))


def clean_cli_block(cli_key: str, block: object) -> dict:
    """Keep only what the operator types in that CLI (rules R2/R3).

    Rows keep ``viento_vel``/``pres_alti``, the observer initials and the
    phenomenon booleans in 3074, and the observer initials plus phenomena in
    4074. The 5074 document
    is stored whole by the owner's decision. Empty strings and ``False``
    booleans never survive.
    """
    if not isinstance(block, dict):
        return {}
    short = cli_key.replace("cli", "")
    if short == "5074":
        return dict(block)
    allowed = OBSERVED_CLI3074 if short == "3074" else OBSERVED_CLI4074
    rows = block.get("horas") if isinstance(block.get("horas"), dict) else block
    cleaned: dict[str, dict] = {}
    for row_key, row in rows.items():
        if not isinstance(row, dict):
            continue
        item: dict = {}
        for field in allowed:
            value = row.get(field)
            if field == "fenomenos":
                if isinstance(value, dict):
                    flags = {k: v for k, v in value.items() if v not in ("", None, False)}
                    if flags:
                        item[field] = flags
            elif value not in ("", None):
                item[field] = value
        if item:
            cleaned[str(row_key)] = item
    if isinstance(block.get("horas"), dict):
        return {"horas": cleaned} if cleaned else {}
    return cleaned


def form_key_for_synop(synop_name: str) -> str | None:
    return _SYNOP_TO_FORM.get(synop_name)


def synop_name_for(form_key: str) -> str | None:
    return _FORM_TO_SYNOP.get(form_key)


def doc_key_for(form_key: str) -> str | None:
    return _FORM_TO_DOC.get(form_key)


def is_derived(form_key: str) -> bool:
    """True when the form key must never be persisted."""
    if form_key in DERIVED_DATOS:
        return True
    return form_key not in _FORM_TO_DOC and form_key not in _FORM_TO_SYNOP


__all__ = [
    "DERIVED_DATOS",
    "OBSERVED_CLI3074",
    "OBSERVED_CLI4074",
    "OBSERVED_DATOS",
    "POLLUTED_9SP_LANES",
    "SYNOP_FIELDS",
    "clean_cli_block",
    "datos_to_document",
    "doc_key_for",
    "document_to_datos",
    "document_to_groups",
    "form_key_for_synop",
    "groups_to_document",
    "is_derived",
    "is_group_value",
    "synop_name_for",
]
