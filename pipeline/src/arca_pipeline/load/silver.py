"""Silver writes: idempotent UPSERT of validated observations.

What it does: upserts validated rows into the silver observations table.
Idempotency: sha256 of the source file is part of the unique key, so re-running
a pipeline over already-loaded data is a no-op — never a duplicate.
What it produces: rows in the `silver_observations` table; returns count of SQL
rows affected.
What it consumes: a SQLAlchemy engine and the validated silver DataFrame.
What it must NOT import: ingest/transform/orchestrate modules.

UPSERT contract (table defined in migrations/, same unique constraint):

    INSERT INTO silver_observations (station_code, fecha, hora, source_sha256, ...)
    VALUES (...)
    ON CONFLICT (station_code, fecha, hora, source_sha256)
    DO UPDATE SET <payload fields> = EXCLUDED.<payload fields>
"""

import pandas as pd
from sqlalchemy import Column, Float, MetaData, PrimaryKeyConstraint, Table, Text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Engine

KEY_COLUMNS = ("station_code", "fecha", "hora", "source_sha256")

# (name, type, nullable) — keep in sync with migrations/versions/0001_initial.py
_COLUMNS = [
    ("station_code", Text, False),
    ("fecha", Text, False),
    ("hora", Text, False),
    ("ts", Float, True),
    ("th", Float, True),
    ("pres_est", Float, True),
    ("pres_nmm", Float, True),
    ("p3", Float, True),
    ("p24", Float, True),
    ("correc_alt", Float, True),
    ("Tmax", Float, True),
    ("Tmin", Float, True),
    ("LL", Float, True),
    ("temp_seco", Float, True),
    ("temp_humedo", Float, True),
    ("hum_ptor", Float, True),
    ("hum_tvap", Float, True),
    ("hum_hr", Float, True),
    ("viento_dir", Text, True),
    ("viento_vel", Float, True),
    ("visibilidad", Float, True),
    ("tend_car", Text, True),
    ("tend_dif", Text, True),
    ("source_sha256", Text, False),
    ("validated_at", Text, True),
]

_metadata = MetaData()
silver_observations = Table(
    "silver_observations",
    _metadata,
    *[Column(name, type_, nullable=nullable) for name, type_, nullable in _COLUMNS],
    PrimaryKeyConstraint(*KEY_COLUMNS),
)


def upsert_observations(engine: Engine, df: pd.DataFrame) -> int:
    """UPSERT all rows of `df` into silver and return the number of affected rows.

    Idempotency: a re-run with the same source_sha256 updates the existing row
    in place — never a duplicate. A corrected file (different sha256) inserts a
    new row, preserving the history of every ingest.
    """
    silver_observations.create(engine, checkfirst=True)
    if df.empty:
        return 0
    payload = [c.name for c in silver_observations.columns if c.name not in KEY_COLUMNS]
    records = df.where(pd.notna(df), None).to_dict("records")
    stmt = insert(silver_observations).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=list(KEY_COLUMNS),
        set_={col: stmt.excluded[col] for col in payload},
    )
    with engine.begin() as conn:
        return conn.execute(stmt).rowcount
