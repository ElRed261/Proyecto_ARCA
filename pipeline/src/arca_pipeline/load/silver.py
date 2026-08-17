"""Silver writes: idempotent UPSERT of validated observations.

What it does: upserts validated rows into the silver observations table.
Idempotency: sha256 of the source file is part of the unique key, so re-running
a pipeline over already-loaded data is a no-op — never a duplicate.
What it produces: rows in the `silver.observations` table; returns count of SQL
rows affected.
What it consumes: a SQLAlchemy engine and the validated silver DataFrame.
What it must NOT import: ingest/transform/orchestrate modules.

UPSERT contract (table defined in migrations/, same unique constraint):

    INSERT INTO silver.observations (station_code, fecha, hora, source_sha256, ...)
    VALUES (...)
    ON CONFLICT (station_code, fecha, hora, source_sha256)
    DO UPDATE SET <payload fields> = EXCLUDED.<payload fields>
"""

from pandas import DataFrame
from sqlalchemy.engine import Engine


def upsert_observations(engine: Engine, df: DataFrame) -> int:
    """UPSERT all rows of `df` into silver and return the number of affected rows."""
    # TODO(load/silver): build the INSERT ... ON CONFLICT statement above
    #   and keep the unique constraint in sync with migrations/.
    raise NotImplementedError