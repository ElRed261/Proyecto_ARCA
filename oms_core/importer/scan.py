"""Directory scanning for the legacy JSON corpus.

Task source: json_handler (layout paths). Two document families exist and
both are recognised wherever they appear under the base root:

- daily observation files, named ``<station> <DDMMYYYY>.json`` (written by
  json_handler::format_date_for_filename), living in
  ``<root>/<station>/<year>/<month>/`` where the station directory may be
  accented or not and the month directory may be zero-padded or not;
- monthly summary files, named ``resumen_<code>_<MMYYYY>.json`` (month
  zero-padded or not), typically at the base root.

The scan is read-only and records a SHA-256 per file for the verification
report.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

DAILY_RE = re.compile(r"^(?P<station>.+) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yyyy>\d{4})\.json$")
RESUMEN_RE = re.compile(r"^resumen_(?P<code>.+?)_(?P<month>\d{1,2})(?P<year>\d{4})\.json$")


@dataclass(frozen=True)
class SourceFile:
    path: Path
    kind: str  # "diario" | "resumen"
    station_code: str
    year: int
    month: int
    day: int | None
    sha256: str
    size: int


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_root(root: Path) -> list[SourceFile]:
    """Classify every *.json file under root, sorted by path for determinism."""
    sources: list[SourceFile] = []
    for path in sorted(root.rglob("*.json")):
        if not path.is_file():
            continue
        name = path.name
        if (match := RESUMEN_RE.match(name)) is not None:
            sources.append(
                SourceFile(
                    path=path,
                    kind="resumen",
                    station_code=match["code"],
                    year=int(match["year"]),
                    month=int(match["month"]),
                    day=None,
                    sha256=sha256_of(path),
                    size=path.stat().st_size,
                )
            )
        elif (match := DAILY_RE.match(name)) is not None:
            sources.append(
                SourceFile(
                    path=path,
                    kind="diario",
                    station_code=match["station"],
                    year=int(match["yyyy"]),
                    month=int(match["mm"]),
                    day=int(match["dd"]),
                    sha256=sha256_of(path),
                    size=path.stat().st_size,
                )
            )
    return sources
