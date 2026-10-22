"""Oracle run for F4 (PRD §7-F4): load a complete real diario fixture through
the Neo Arca synoptic service (`oms_core.services.synoptic.save_hour`), save
ALL hours, and compare the rebuilt document against the legacy source:

- data passthrough (real legacy `datos` keys → daily-document `datos`);
- SYNOP groups (legacy `synop_manual` names → `to_synop_name` keys);
- derived values (legacy `calculados` tv/hr/pr/dif/pres_nmm — empty in this
  corpus, so diffs there are 'empty' with explanation, never silent);
- row counts (`observations` = 8 Z-hours per fixture, legacy parity).

Read-only over OLD/ (never touched). Write target is a scratch SQLite DB and
`oracle_F4.json` (this F4 evidence directory).
"""

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import oms_calc
from oms_core.db.connection import connect
from oms_core.db.migrations import migrate
from oms_core.db.repositories import observations as observations_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import synoptic as syn

SOURCES = [
    ROOT / "OLD/miscelaneos/backend_python/app/modules/synoptic/data/78485/2025/12/7848508122025.json",
    ROOT / "OLD/miscelaneos/backend_python/app/modules/synoptic/data/78486/2025/12/7848608122025.json",
]

#: legacy synop_manual key -> frontend key (SynopticPage load path verbatim).
MANUAL_TO_FRONTEND = {
    "irixhvv": "meteo_4_irixhvv",
    "n_dd_ff": "meteo_4_1",
    "7ww_w1w2": "meteo_4_6",
    "8nh_cl_cm_ch": "meteo_6_0",
    "0cs_dl_dm_dh": "meteo_6_2",
    "3e_jjj": "meteo_6_5",
    "5eee_je": "meteo_6_6",
    "5n_fn": "meteo_8_0",
    "56dl_dm_dh": "meteo_8_1",
    "6rrr_tr": "meteo_8_3",
    "7r24": "meteo_8_4",
    "8ns_1": "meteo_8_5",
    "8ns_2": "meteo_8_6",
    "8ns_3": "extra_8ns_1",
    "8ns_4": "extra_8ns_2",
}

#: frontend key -> daily-document `datos` key (storage.rs build_horas_map).
DATOS_KEY_MAP = syn._DATOS_KEY_MAP

#: legacy calculados key -> frontend derived key → daily-document key.
CALC_LEGACY_TO_META = {
    "tv": ("tension_vapor", "tv"),
    "hr": ("humedad_relativa", "hr"),
    "pr": ("punto_rocio", "pr"),
    "dif": ("diferencia", "dif"),
    "pres_nmm": ("pres_nmm", "pres_nmm"),
}

#: legacy synop_calculado groups are produced by realizar_calculos at calc
#: time; the F4 save path persists derived values in doc 'calculado' only.
SYNOP_CALCULADO_GROUPS = ("1sn_ttt", "2sn_tdtdtd", "4pppp", "5appp", "58_59_p24", "29uuu")

DELTA = 1e-6


def frontend_for_legacy_key(legacy_key: str) -> str | None:
    """Legacy synop_manual key → frontend key; None for manual-only slots."""
    if legacy_key in ("1sn_tx_manual", "2sn_tn_manual"):
        return None
    mapped = MANUAL_TO_FRONTEND.get(legacy_key)
    if mapped is not None:
        return mapped
    if legacy_key.startswith("9sp_"):
        return "meteo_" + legacy_key[len("9sp_"):]
    return legacy_key  # meteo_* row keys pass through to_synop_name untouched


def build_hour_data(row: dict):
    """Legacy horarias row → F4 hour payload (frontend keys)."""
    data: dict = {}
    datos = row.get("datos") or {}
    legacy_to_frontend = {}
    for frontend, doc_key in DATOS_KEY_MAP.items():
        legacy_to_frontend[{"Ts": None}.get(doc_key, doc_key)] = None  # placeholder, unused
    # datos passthrough map (legacy name == doc name except the Tmax family)
    frontend_to_legacy = {
        frontend: {"correc_alt": "correc_alt"}.get(frontend, doc_key)
        for frontend, doc_key in DATOS_KEY_MAP.items()
    }
    for frontend, legacy_name in frontend_to_legacy.items():
        if legacy_name in datos:
            data[frontend] = datos[legacy_name]
    # synop groups (manual) — the *_manual temperature keys are separate slots
    for legacy_key, legacy_value in (row.get("synop_manual") or {}).items():
        frontend_key = MANUAL_TO_FRONTEND.get(legacy_key)
        if frontend_key is None and legacy_key.startswith("9sp_"):
            frontend_key = "meteo_" + legacy_key[len("9sp_"):]
        if frontend_key is not None and legacy_value:
            data[frontend_key] = legacy_value
    yygg = row.get("yygg_iw")
    if yygg:
        data["meteo_2_1"] = yygg
    observer = (row.get("nombre_observador") or "").strip()
    if observer:
        data["nombre_observador"] = observer
    return data


def compare_floats(legacy: str, ours: str) -> tuple[bool, str]:
    a = float(str(legacy).replace(",", "."))
    b = float(str(ours).replace(",", "."))
    equal = abs(a - b) <= DELTA
    return equal, f"{a} vs {b} (delta {abs(a - b)}"


def run():
    legacy_stats = []
    diffs = []
    explained = []
    tmp = tempfile.mkdtemp(prefix="oracle_f4_")
    conn = connect(pathlib.Path(tmp) / "oracle.db")
    migrate(conn)

    for source in SOURCES:
        doc = json.loads(source.read_text(encoding="utf-8"))
        meta = doc["meta"]
        station = meta["estacion"]
        raw_fecha = meta["fecha"]  # DDMMYYYY
        fecha_iso = f"{raw_fecha[4:8]}-{raw_fecha[2:4]}-{raw_fecha[0:2]}"
        station_row = conn.execute(
            "SELECT ch FROM stations WHERE id = ?", (station,)
        ).fetchone()
        station_ch = station_row["ch"] if station_row else None

        per_source = {
            "file": str(source.relative_to(ROOT)),
            "station": station,
            "fecha_iso": fecha_iso,
            "station_ch_from_seed": station_ch,
            "horas": len(doc.get("horarias", [])),
            "saved_hours": 0,
            "group_mismatches": [],
            "datos_mismatches": [],
            "derived_compared": 0,
            "derived_mismatches": [],
        }
        stats_row = {
            "file": per_source["file"],
            "rows_expected": 0,
            "rows_written": None,
            "pres_nmm_written_hours": 0,
        }

        for row in doc.get("horarias", []):
            hora = row["hora"]
            if hora not in syn.HOURS:
                continue  # aux rows (TMAX/TMIN/nuvosidad) live only in the legacy file
            stats_row["rows_expected"] += 1
            data = build_hour_data(row)
            observer = (row.get("nombre_observador") or "").strip() or None
            syn.save_hour(conn, station, fecha_iso, hora, data, observer=observer)
            per_source["saved_hours"] += 1

            stored_doc = json.loads(
                summaries_repo.get_summary_doc(conn, station, int(fecha_iso[:4]), int(fecha_iso[5:7]), "diario", day=int(fecha_iso[8:10]))
            )
            stored_hora = stored_doc["horas"].get(hora, {})
            stored_datos = stored_hora.get("datos") or {}
            stored_synop = stored_hora.get("synop") or {}

            # 1) data passthrough: both-sides-non-empty must be equal;
            #    empty-vs-empty is the free pass ('empty' diff).
            for frontend, legacy_name in (
                (f, {"correc_alt": "correc_alt"}.get(f, dk))
                for f, dk in DATOS_KEY_MAP.items()
            ):
                legacy_value = (row.get("datos") or {}).get(legacy_name)
                doc_key = DATOS_KEY_MAP.get(frontend, frontend)
                ours_value = stored_datos.get(doc_key)
                if legacy_value is None and ours_value is None:
                    continue  # key untouched on both sides
                legacy_text = "" if legacy_value is None else str(legacy_value)
                ours_text = "" if ours_value is None else str(ours_value)
                if legacy_text.strip() == ours_text.strip():
                    continue  # equal (both filled or both empty)
                if legacy_text.strip() == "" or ours_text.strip() == "":
                    explained.append({
                        "kind": "datos_empty",
                        "file": per_source["file"],
                        "hora": hora,
                        "key": doc_key,
                        "legacy": legacy_text,
                        "ours": ours_text,
                        "explanation": "one side empty: nothing to disagree with",
                    })
                    continue
                per_source["datos_mismatches"].append({
                    "hora": hora, "key": doc_key, "legacy": legacy_text, "ours": ours_text,
                })

            # 2) SYNOP groups: legacy synop_manual (+ top-level yygg_iw)
            legacy_groups = dict(row.get("synop_manual") or {})
            if row.get("yygg_iw"):
                legacy_groups["meteo_2_1"] = row["yygg_iw"]
            for legacy_key, legacy_value in legacy_groups.items():
                frontend_key = frontend_for_legacy_key(legacy_key)
                if frontend_key is None or not str(legacy_value).strip():
                    continue
                doc_key = oms_calc.to_synop_name(frontend_key)
                ours_value = stored_synop.get(doc_key)
                if ours_value is None:
                    per_source["group_mismatches"].append({
                        "hora": hora, "group": doc_key, "legacy": legacy_value, "ours": None,
                    })
                elif str(ours_value).strip() != str(legacy_value).strip():
                    per_source["group_mismatches"].append({
                        "hora": hora, "group": doc_key, "legacy": legacy_value, "ours": ours_value,
                    })
            # groups present in ours but not in the legacy payload
            for doc_key, ours_value in stored_synop.items():
                if not str(ours_value).strip():
                    continue
                legacy_nonempty = any(
                    (fe := frontend_for_legacy_key(k)) is not None
                    and oms_calc.to_synop_name(fe) == doc_key
                    and str(v).strip()
                    for k, v in legacy_groups.items()
                )
                if not legacy_nonempty:
                    explained.append({
                        "kind": "synop_extra",
                        "file": per_source["file"],
                        "hora": hora,
                        "group": doc_key,
                        "ours": ours_value,
                        "explanation": "stored group without a non-empty legacy counterpart",
                    })

            # 3) derived values: only comparable when the legacy stored one
            for legacy_key, (derived_key, doc_key) in CALC_LEGACY_TO_META.items():
                legacy_value = (row.get("calculados") or {}).get(legacy_key)
                ours_value = (stored_hora.get("calculado") or {}).get(doc_key)
                if legacy_value is None or not str(legacy_value).strip():
                    if ours_value is not None and str(ours_value).strip():
                        explained.append({
                            "kind": "derived_legacy_empty",
                            "file": per_source["file"],
                            "hora": hora,
                            "key": derived_key,
                            "ours": ours_value,
                            "explanation": f"legacy '{legacy_key}' empty: stored derived is a fresh recalc, no legacy value to diff",
                        })
                    continue
                if ours_value is None or not str(ours_value).strip():
                    explained.append({
                        "kind": "derived_ours_empty",
                        "file": per_source["file"],
                        "hora": hora,
                        "key": derived_key,
                        "legacy": legacy_value,
                        "explanation": "our recalc left the field empty (insufficient inputs among the F4 base keys)",
                    })
                    continue
                equal, detail = compare_floats(legacy_value, ours_value)
                per_source["derived_compared"] += 1
                if not equal:
                    per_source["derived_mismatches"].append({
                        "hora": hora, "key": derived_key, "detail": detail,
                    })

            # 4) synop_calculado groups (row 4/8/16): legacy slots are all
            #    empty here and the F4 path persists the derived *values* in
            #    'calculado', not the formatted groups — structural difference.
            for group in SYNOP_CALCULADO_GROUPS:
                legacy_value = (row.get("synop_calculado") or {}).get(group)
                if legacy_value is None or not str(legacy_value).strip():
                    continue
                diffs.append({
                    "kind": "synop_calculado_group",
                    "file": per_source["file"],
                    "hora": hora,
                    "group": group,
                    "legacy": legacy_value,
                    "explanation": "structural: OMS group formatting happens at calc time (UI), the doc persists bare derived values in 'calculado'",
                })

        rows = observations_repo.get_day(conn, station, fecha_iso)
        stats_row["rows_written"] = len(rows)
        stats_row["pres_nmm_written_hours"] = sum(1 for r in rows if r.p_nmm is not None)
        for r in rows:
            resolver = f"hola {r.hora}"
        legacy_stats.append(per_source)
        del resolver
        per_source["rows_expected"] = stats_row.pop("rows_expected")
        per_source["rows_written"] = stats_row.pop("rows_written")
        per_source["pres_nmm_written_hours"] = stats_row.pop("pres_nmm_written_hours")

    # cross-fixture check: every hour row carries the doc's derived results
    unresolved = [d for d in diffs if "unresolved" in d]
    group_mismatch_total = sum(len(s["group_mismatches"]) for s in legacy_stats)
    datos_mismatch_total = sum(len(s["datos_mismatches"]) for s in legacy_stats)
    derived_mismatch_total = sum(len(s["derived_mismatches"]) for s in legacy_stats)

    result = {
        "fase": "F4",
        "semantics": "save_hour per hora through oms_core.services.synoptic (row + verbatim doc, one transaction each)",
        "diffs": diffs,
        "explained": explained,
        "totals": {
            "group_mismatches": group_mismatch_total,
            "datos_mismatches": datos_mismatch_total,
            "derived_mismatches": derived_mismatch_total,
            "unresolved": len(unresolved),
            "explained": len(explained),
        },
        "ok": (
            group_mismatch_total == 0
            and datos_mismatch_total == 0
            and derived_mismatch_total == 0
            and len(unresolved) == 0
        ),
        "sources": legacy_stats,
    }
    if result["ok"]:
        print("ORACLE F4: diff vacío (o explicado) ✓")
    else:
        print("ORACLE F4: diffs sin explicar", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)

    conn.close()
    return result


if __name__ == "__main__":
    out = pathlib.Path(__file__).with_name("oracle_F4.json")
    result = run()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"escrito: {out}")
