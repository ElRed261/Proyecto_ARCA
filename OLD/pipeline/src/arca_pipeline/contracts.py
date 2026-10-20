"""Shared versioned contracts between layers.

What it does: defines the payload shapes that cross layer boundaries
(bronze -> silver) so ingest/transform/load never guess each other's formats.
What it produces: stable dataclasses for metadata and per-row records.
What it consumes: nothing.
What it must NOT import: any pipeline module (it is the dependency root).

Versioning: bump SCHEMA_VERSION on any breaking change to these contracts.
"""

from dataclasses import dataclass
from datetime import datetime

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BronzeMeta:
    """Raw-file registration record written to the bronze layer before parsing."""

    source_file: str
    sha256: str
    ingested_at: datetime
    drive_modified_time: str
    size: int


@dataclass(frozen=True)
class SilverRow:
    """One validated meteorological observation.

    Only base fields are present today. The WMO physical fields
    (temperature, humidity, pressure, wind, precip, ...) are filled in during
    the transform phase (see transform/excel_to_json.py) and must be added
    here together with their pandera ranges in validate/contracts.py.
    """

    station_code: str
    fecha: str  # YYYY-MM-DD
    hora: str  # HHZ, e.g. "06Z"
    source_sha256: str
    validated_at: datetime