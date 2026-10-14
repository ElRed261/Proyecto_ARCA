"""Gold writes: monthly KPI aggregates for a station.

What it does: recomputes monthly statistics for one station and upserts them
into the gold tables (see sql/kpis.sql). Runs after the silver load wraps for
the period covered by the run.
What it produces: rows in the gold layer derived from silver only.
What it consumes: a SQLAlchemy engine plus the station/month to aggregate.
What it must NOT import: ingest/transform/orchestrate modules.

Layering rule: gold NEVER reads bronze; it only aggregates silver.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from arca_pipeline.load.silver import silver_observations

_metadata = MetaData()
gold_kpis_mensuales = Table(
    "gold_kpis_mensuales",
    _metadata,
    Column("station_code", Text, nullable=False),
    Column("year", Integer, nullable=False),
    Column("month", Integer, nullable=False),
    Column("avg_ts", Float),
    Column("avg_th", Float),
    Column("avg_pres_nmm", Float),
    Column("min_Tmin", Float),
    Column("max_Tmax", Float),
    Column("avg_hum_hr", Float),
    Column("days_with_data", Integer),
    Column("created_at", Text),
    PrimaryKeyConstraint("station_code", "year", "month"),
)


def build_monthly_kpis(engine: Engine, station_code: str, year: int, month: int) -> dict:
    """Recompute gold monthly KPIs for (station_code, year, month) and upsert them.

    Returns the computed KPI dict. Idempotent: re-running upserts the same
    (station_code, year, month) key instead of growing the table.
    """
    silver_observations.create(engine, checkfirst=True)
    gold_kpis_mensuales.create(engine, checkfirst=True)
    agg = (
        select(
            func.avg(silver_observations.c.ts).label("avg_ts"),
            func.avg(silver_observations.c.th).label("avg_th"),
            func.avg(silver_observations.c.pres_nmm).label("avg_pres_nmm"),
            func.min(silver_observations.c.Tmin).label("min_Tmin"),
            func.max(silver_observations.c.Tmax).label("max_Tmax"),
            func.avg(silver_observations.c.hum_hr).label("avg_hum_hr"),
            func.count(func.distinct(silver_observations.c.fecha)).label("days_with_data"),
        )
        .where(silver_observations.c.station_code == station_code)
        .where(silver_observations.c.fecha.like(f"{year:04d}-{month:02d}%"))
    )
    with engine.begin() as conn:
        row = conn.execute(agg).one()
        values = {
            "station_code": station_code,
            "year": year,
            "month": month,
            "avg_ts": row.avg_ts,
            "avg_th": row.avg_th,
            "avg_pres_nmm": row.avg_pres_nmm,
            "min_Tmin": row.min_Tmin,
            "max_Tmax": row.max_Tmax,
            "avg_hum_hr": row.avg_hum_hr,
            "days_with_data": int(row.days_with_data or 0),
            "created_at": datetime.now(UTC).isoformat(),
        }
        # ponytail: dialect-aware upsert — default deployment is postgres, tests use sqlite;
        # both dialect inserts expose identical on_conflict_do_update API
        insert = sqlite_insert if engine.dialect.name == "sqlite" else postgresql_insert
        stmt = insert(gold_kpis_mensuales).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["station_code", "year", "month"],
            set_={k: stmt.excluded[k] for k in values if k not in ("station_code", "year", "month")},
        )
        conn.execute(stmt)
    return values