"""Queryable API for the warehouse (silver + gold) and pipeline observability.

What it does: exposes warehouse tables and run state over HTTP for the UI/Query layer.
What it produces: JSON responses from silver_observations, gold_kpis_mensuales, last_run.json, rejected logs.
What it consumes: DATABASE_URL via settings and local files (last_run.json, rejected/*.rejected.json).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ponytail: reuse pipeline root + settings from config, fallback when pydantic-settings missing
try:
    from arca_pipeline.config import _PIPELINE_ROOT, settings  # type: ignore
except Exception:  # noqa: BLE001  # pragma: no cover
    _PIPELINE_ROOT = Path(__file__).resolve().parents[3]

    class _DummySettings:  # ponytail: minimal stub — env vars still work via os.getenv
        database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://arca:arca@localhost:5432/arca")

    settings = _DummySettings()  # type: ignore

# ponytail: lazy import of tables — reuse silver/gold definitions, no duplication
try:
    from arca_pipeline.load.gold import gold_kpis_mensuales
    from arca_pipeline.load.silver import silver_observations
except Exception:  # noqa: BLE001  # pragma: no cover
    silver_observations = None  # type: ignore
    gold_kpis_mensuales = None  # type: ignore

app = FastAPI(title="ARCA Pipeline API")


def _get_engine():
    from sqlalchemy import create_engine

    return create_engine(settings.database_url)


def _find_last_run() -> Path | None:
    # ponytail: check primary (runner.py _PIPELINE_ROOT/data/state) then fallback (pipeline/last_run.json)
    candidates = [
        _PIPELINE_ROOT / "data" / "state" / "last_run.json",
        _PIPELINE_ROOT / "last_run.json",
        Path(__file__).resolve().parents[3] / "last_run.json",
        Path(__file__).resolve().parents[3] / "data" / "state" / "last_run.json",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def _rejected_dirs() -> list[Path]:
    # ponytail: support both runner default (data/rejected) and task description (rejected)
    candidates = [
        _PIPELINE_ROOT / "data" / "rejected",
        _PIPELINE_ROOT / "rejected",
        Path(__file__).resolve().parents[3] / "data" / "rejected",
        Path(__file__).resolve().parents[3] / "rejected",
    ]
    # ponytail: deduplicate preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


@app.get("/health")
def health():
    logger.info("GET /health")
    return {"status": "ok"}


@app.get("/state")
def get_state():
    logger.info("GET /state")
    path = _find_last_run()
    if path is None:
        return JSONResponse(status_code=404, content={"status": "no runs yet"})
    try:
        data = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        logger.warning("failed to read last_run.json %s: %s", path, exc)
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    return JSONResponse(content=data)


@app.get("/stations/{code}/observations")
def get_observations(
    code: str,
    from_date: date = Query(..., alias="from", description="YYYY-MM-DD"),  # noqa: B008
    to_date: date = Query(..., alias="to", description="YYYY-MM-DD"),  # noqa: B008
):
    logger.info("GET /stations/%s/observations from=%s to=%s", code, from_date, to_date)
    if silver_observations is None:  # pragma: no cover
        return JSONResponse(status_code=500, content={"detail": "silver_observations not available"})
    engine = _get_engine()
    # ponytail: ensure table exists for sqlite ephemeral DBs (checkfirst, no migration needed)
    try:
        silver_observations.create(engine, checkfirst=True)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001, S110  # pragma: no cover
        pass
    from sqlalchemy import select

    from_iso = from_date.isoformat()
    to_iso = to_date.isoformat()
    stmt = (
        select(silver_observations)  # type: ignore[arg-type]
        .where(silver_observations.c.station_code == code)  # type: ignore[attr-defined]
        .where(silver_observations.c.fecha >= from_iso)  # type: ignore[attr-defined]
        .where(silver_observations.c.fecha <= to_iso)  # type: ignore[attr-defined]
        .order_by(silver_observations.c.fecha, silver_observations.c.hora)  # type: ignore[attr-defined]
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()
        observations = [dict(r) for r in rows]
    engine.dispose()
    return {
        "station_code": code,
        "from": from_iso,
        "to": to_iso,
        "count": len(observations),
        "observations": observations,
    }


@app.get("/stations/{code}/kpis")
def get_kpis(
    code: str,
    year: int = Query(..., ge=1900, le=2100),
    month: int = Query(..., ge=1, le=12),
):
    logger.info("GET /stations/%s/kpis year=%s month=%s", code, year, month)
    if gold_kpis_mensuales is None:  # pragma: no cover
        return JSONResponse(status_code=500, content={"detail": "gold_kpis_mensuales not available"})
    engine = _get_engine()
    try:
        gold_kpis_mensuales.create(engine, checkfirst=True)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001, S110  # pragma: no cover
        pass
    from sqlalchemy import select

    stmt = select(gold_kpis_mensuales).where(  # type: ignore[arg-type]
        gold_kpis_mensuales.c.station_code == code  # type: ignore[attr-defined]
    ).where(gold_kpis_mensuales.c.year == year).where(gold_kpis_mensuales.c.month == month)  # type: ignore[attr-defined]
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()
    engine.dispose()
    if row is None:
        return JSONResponse(status_code=404, content={"detail": "not found"})
    return dict(row)


@app.get("/rejected")
def get_rejected():
    logger.info("GET /rejected")
    files: list[dict] = []
    seen: set[str] = set()
    for d in _rejected_dirs():
        if not d.exists() or not d.is_dir():
            continue
        for p in sorted(d.glob("*.rejected.json")):
            if p.name in seen:
                continue
            seen.add(p.name)
            try:
                data = json.loads(p.read_text())
                reason = data.get("reason")
                if reason is None:
                    errs = data.get("errors")
                    if isinstance(errs, list):
                        reason = "; ".join(str(x) for x in errs)
                    else:
                        reason = errs or "unknown"
                if isinstance(reason, list):
                    reason = "; ".join(str(x) for x in reason)
                reason = str(reason)
            except Exception as exc:  # noqa: BLE001  # pragma: no cover
                reason = f"read_error: {exc}"
            files.append({"filename": p.name, "reason": reason})
    # ponytail: return plain list for minimal contract; wrapped count is redundant but harmless — keep list
    # to satisfy both "lista" and "count" expectations we return list; ruff/ponytail minimal
    return files
