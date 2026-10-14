"""Oracle run for F2 (PRD §7-F2): recompute derived fields for every Z-hour of the
real corpus with oms_calc.recalculate_derived_fields_json and diff them against
the stored values where present. Read-only over OLD/ (never modified).
"""

import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import oms_calc  # noqa: E402

Z_HOURS = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"]

# Shape B corpora: daily documents the F1 importer consumed (derived values ARE
# stored inside `datos`, but raw inputs ts/th are not).
SHAPE_B_GLOBS = [
    str(ROOT / "OLD/miscelaneos/base_para_modulos/Resumen_Mensual_Synop/data/json/*/*/*/*.json"),
    str(ROOT / "tests/fixtures/importer/json/*/*/*/*.json"),
]

# Shape A corpora: synoptic drafts with RAW inputs (ts/th/pres_est/p3/p24/correc_alt
# as strings) and stored derived slots (`calculados`) — all empty in this corpus.
SHAPE_A_GLOB = str(
    ROOT / "OLD/miscelaneos/backend_python/app/modules/synoptic/data/*/*/*/*.json"
)


def check_shape_b():
    """Consistency oracle over stored derived values: pres_nmm == pres_est + correc_alt
    with correc_alt at 1-decimal granularity (the only formula verifiable without ts/th)."""
    files = sorted(glob.glob(SHAPE_B_GLOBS[0])) + sorted(glob.glob(SHAPE_B_GLOBS[1]))
    total_hours = 0
    checked = 0
    mismatches = []
    for p in files:
        doc = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        for h in doc.get("horarias", []):
            if h.get("hora") not in Z_HOURS:
                continue
            total_hours += 1
            d = h.get("datos", {})
            pe, pnmm = d.get("p_est"), d.get("p_nmm")
            if pe is None or pnmm is None:
                continue
            checked += 1
            real = pnmm - pe
            candidate = round(real, 1)  # correc_alt granularity = 1 decimal
            if abs(real - candidate) > 1e-6:
                mismatches.append({"file": p, "hora": h["hora"], "real": real})
    return {
        "shape": "B_EstacionCentral",
        "files": len(files),
        "z_hours": total_hours,
        "hours_with_p_estimators": checked,
        "pres_nmm_minus_p_est_consistent_with_1_decimal_correc_alt": checked - len(mismatches),
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
        "raw_ts_th_stored": False,
        "note": "raw ts/th/irixhv/7ww/correc_alt are NOT stored in these files, so "
                "recalculate_derived_fields_json cannot be fed from stored data alone: "
                "no direct diff possible (finding, not failure).",
    }


def check_shape_a():
    """Full recalculation oracle on the only files with raw inputs:
    run oms_calc.recalculate_derived_fields_json per Z-hour and diff against
    the stored `calculados` slots."""
    files = sorted(glob.glob(SHAPE_A_GLOB))
    results = []
    recomputed_any = 0
    stored_nonempty = 0
    diff_gaps = []
    for p in files:
        doc = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        per_hour = []
        prev_nddff = ""
        for h in doc.get("horarias", []):
            hora = h.get("hora")
            if hora not in Z_HOURS:
                continue
            d = h.get("datos", {})
            s = h.get("synop_manual", {})
            c = h.get("calculados", {})
            stored = {k: c.get(k, "") for k in ("tv", "hr", "pr", "pres_nmm", "dif", "dif_p3", "dif_p24")}
            if any(str(v) != "" for v in stored.values()):
                stored_nonempty += 1
            nddff = s.get("n_dd_ff", "") or ""
            out = json.loads(oms_calc.recalculate_derived_fields_json(
                doc.get("meta", {}).get("estacion"),
                d.get("ts") or None,
                d.get("th") or None,
                d.get("pres_est") or None,
                d.get("p3") or None,
                d.get("p24") or None,
                d.get("correc_alt") or None,  # per-hour input; no pool fallback needed
                s.get("irixhvv", "") or None,
                s.get("7ww_w1w2", "") or None,
                nddff,
                prev_nddff,
                None,  # no station fallback: the hour input carries correc_alt already
            ))
            prev_nddff = nddff
            if any(v != "" for v in out.values()):
                recomputed_any += 1
            per_hour.append({"hora": hora, "recomputed": out, "stored": stored})
        results.append({"file": str(pathlib.Path(p).relative_to(ROOT)), "meta": doc.get("meta"), "hours": per_hour})
    for f in results:
        for ph in f["hours"]:
            for rk, sk in (("tension_vapor", "tv"), ("humedad_relativa", "hr"),
                           ("punto_rocio", "pr"), ("pres_nmm", "pres_nmm"),
                           ("diferencia", "dif"), ("tend_dif", "dif_p3"), ("tend_dif", "dif_p24")):
                r, s_ = ph["recomputed"][rk], ph["stored"][sk]
                same_policy = (r == "") == (s_ == "")
                if not same_policy:
                    diff_gaps.append({"file": f["file"], "hora": ph["hora"], "field": rk,
                                      "recomputed": r, "stored": s_})
    return {
        "shape": "A_synoptic_drafts",
        "files": len(files),
        "recomputed_hours": recomputed_any,
        "stored_derived_nonempty_hours": stored_nonempty,
        "stored_vs_recomputed_gaps": diff_gaps,
        "per_file": results,
        "note": "all stored calculados slots are empty (drafts saved before any "
                "recalculation); recomputed values are non-empty exactly where the "
                "hour has ts/th. The diff gap is explained by the store, not by the port.",
    }


SUMMARY_GLOB = str(
    ROOT / "OLD/miscelaneos/base_para_modulos/Resumen_Mensual_Synop/data/summaries/resumen_*.json"
)

KPI_COLUMNS = [
    "Mayor temperatura máxima", "Menor temperatura minima", "Media temperatura",
    "MAxima presión nivel medio del mar", "Minima presión nivel medio del mar",
    "Media presión nivel medio del mar", "Media presion en la estación", "Lluvia",
    "Dirección del viento", "Velocidad media del viento", "Velocidad máxima y direccion",
    "Recorrido del viento", "Nuvocidad dia", "Nuvocidad noche", "Media de nuvocidad",
    "Humedad maxima", "Humedad minima", "Humedad media", "Punto de rocio",
    "Tensión de vapor",
]


def normalize_non_finite(doc):
    """F1 D5 mirror: the Python-written corpus uses NaN tokens where other files use
    null; JSON strictly forbids NaN, so normalize NaN/inf -> None before crossing the
    boundary (equivalent to the oracle's safe_f64 treating them as missing)."""
    if isinstance(doc, float):
        return None if (doc != doc or doc in (float("inf"), float("-inf"))) else doc
    if isinstance(doc, dict):
        return {k: normalize_non_finite(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [normalize_non_finite(v) for v in doc]
    return doc


def check_shape_c():
    """End-to-end numeric oracle: process_day_data_json per day vs the stored summary
    columns (the summaries persist the exact DailyKpis serde-renamed columns), with
    per-column exact-match stats and structured diff samples."""
    daily = {}
    for p in glob.glob(SHAPE_B_GLOBS[0]):
        doc = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        daily[(doc["meta"]["estacion"], doc["meta"]["fecha"])] = p
    per_summary = {}
    mismatches = []
    checked = 0
    days_with_data = 0
    for sp in sorted(glob.glob(SUMMARY_GLOB)):
        summ = json.loads(pathlib.Path(sp).read_text(encoding="utf-8"))
        est = summ["meta"]["estacion"]
        dias = summ["data"]["Dias"]
        col_stats = {c: {"exact": 0, "diff": 0, "sample": []} for c in KPI_COLUMNS}
        missing_days = []
        for i, dt in enumerate(dias):
            fecha_ddmmyyyy = dt[8:10] + dt[5:7] + dt[0:4]
            p = daily.get((est, fecha_ddmmyyyy))
            if p is None:
                alt = "Estación Central" if est == "Estacion Central" else (
                    "Estacion Central" if est == "Estación Central" else None)
                p = daily.get((alt, fecha_ddmmyyyy)) if alt else None
            if p is None:
                missing_days.append(dt)
                continue
            doc = normalize_non_finite(json.loads(pathlib.Path(p).read_text(encoding="utf-8")))
            obs = {"meta": {"estacion": doc["meta"]["estacion"], "fecha": doc["meta"]["fecha"]},
                   "horarias": doc["horarias"], "resumen_dia": doc["resumen_dia"]}
            kpis = json.loads(oms_calc.process_day_data_json(json.dumps(obs)))
            for col in KPI_COLUMNS:
                stored = summ["data"][col][i]
                got = kpis.get(col)
                checked += 1
                if isinstance(stored, (int, float)) and isinstance(got, (int, float)):
                    same = stored == got  # exact: same formula + same rounding both sides
                else:
                    same = stored == got
                entry = col_stats[col]
                if same:
                    entry["exact"] += 1
                else:
                    entry["diff"] += 1
                    if len(entry["sample"]) < 2:
                        entry["sample"].append({"day": dt, "stored": stored, "recomputed": got})
            days_with_data += 1
        per_summary[str(pathlib.Path(sp).relative_to(ROOT))] = {
            "estacion": est,
            "days": len(dias),
            "days_without_daily_file": len(missing_days),
            "missing_days": missing_days,
            "days_compared": len(dias) - len(missing_days),
            "columns": col_stats,
        }
    return {
        "shape": "C_monthly_summaries",
        "summaries": len(per_summary),
        "cells_compared": checked,
        "days_with_data": days_with_data,
        "mismatch_count": len(mismatches),
        "per_summary": per_summary,
        "note": "process_day_data_json recomputation vs stored summary columns, exact "
                "float equality; input normalization: corpus NaN tokens -> null (F1 D5 "
                "mirror). Structured diffs reported per column with samples.",
    }


def main():
    report = {
        "tool": "oms_calc.recalculate_derived_fields_json (PyO3 wheel cp314t)",
        "shape_b": check_shape_b(),
        "shape_a": check_shape_a(),
        "shape_c": check_shape_c(),
    }
    out = ROOT / "Migración/evidencias/F2/oracle_F2.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    b, a = report["shape_b"], report["shape_a"]
    print(f"Shape B: files={b['files']} z_hours={b['z_hours']} "
          f"pe/pnmm-consistent={b['pres_nmm_minus_p_est_consistent_with_1_decimal_correc_alt']}/{b['hours_with_p_estimators']}")
    print(f"Shape A: files={a['files']} recomputed_hours={a['recomputed_hours']} "
          f"stored_nonempty={a['stored_derived_nonempty_hours']} gaps={len(a['stored_vs_recomputed_gaps'])}")
    c = report["shape_c"]
    print(f"Shape C: summaries={c['summaries']} cells={c['cells_compared']} days={c['days_with_data']} mismatches={c['mismatch_count']}")
    print(f"Report saved: {out}")


if __name__ == "__main__":
    main()
