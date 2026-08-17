"""Gold writes: monthly KPI aggregates for a station.

What it does: recomputes monthly statistics for one station and upserts them
into the gold tables (see sql/kpis.sql). Runs after the silver load wraps for
the period covered by the run.
What it produces: rows in the gold layer derived from silver only.
What it consumes: a SQLAlchemy engine plus the station/month to aggregate.
What it must NOT import: ingest/transform/orchestrate modules.

Layering rule: gold NEVER reads bronze; it only aggregates silver.
"""

from sqlalchemy.engine import Engine


def build_monthly_kpis(engine: Engine, station_code: str, year: int, month: int) -> None:
    """Recompute gold monthly KPIs for (station_code, year, month)."""
    # TODO(load/gold): run the aggregation SQL from sql/kpis.sql for the month,
    #   upserting into gold.monthly_kpis keyed on (station_code, year, month).
    raise NotImplementedError