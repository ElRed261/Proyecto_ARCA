"""Pandera data contracts for the bronze -> silver boundary.

What it does: validates every observation row BEFORE it enters silver so the
silver layer only ever contains physically plausible data.
What it produces: a validated pandas DataFrame (or raises SchemaError).
What it consumes: the DataFrame produced by transform/.
What it must NOT import: load/orchestrate modules.

Physical ranges follow WMO guidance and get ENFORCED as soon as the transform
layer produces the fields:

    temperature_c: [-60, 60]     # °C
    humidity_pct: [0, 100]       # relative humidity
    pressure_hpa: [850, 1100]    # sea-level pressure
    wind_speed_ms: [0, 90]       # m/s
    precip_mm: [0, 1000]         # daily accumulation

Validation happens at the boundary on purpose: rejected rows go to the
rejected/ area with their raw payload, never into silver.
"""

import pandera as pa
from pandera import DataFrameModel
from pandera.typing import DataFrame, Series


class SilverSchema(DataFrameModel):
    """Base columns every silver row must satisfy.

    WMO physical fields are added here together with the transform phase;
    their range checks are documented in the module docstring above.
    """

    station_code: Series[str] = pa.Field(isin=["3074"])  # known stations; expand as new ones are added
    fecha: Series[str] = pa.Field(str_matches=r"^\d{4}-\d{2}-\d{2}$")
    hora: Series[str] = pa.Field(str_matches=r"^\d{2}Z$")
    source_sha256: Series[str] = pa.Field(str_length={"min_value": 64, "max_value": 64})

    # Example once transform emits the field:
    # temperature_c: Series[float] = pa.Field(ge=-60.0, le=60.0)
    # humidity_pct: Series[float] = pa.Field(ge=0.0, le=100.0)
    # pressure_hpa: Series[float] = pa.Field(ge=850.0, le=1100.0)


def validate_silver(df: DataFrame) -> DataFrame:
    """Validate `df` against SilverSchema; returns the (possibly cast) DataFrame."""
    return SilverSchema.validate(df)