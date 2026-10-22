"""Importer core: parse -> transactional upsert -> §6.3 verification report.

Flow per run (single transaction; every upsert is keyed by the natural key,
so re-running against the same corpus lands on the exact same rows):

1. scan both legacy layouts/month namings (see scan.py);
2. parse both document shapes (see parse.py); broken files are reported and
   do not abort the run — but the report is ``ok=False``;
3. station keys come from the document meta, verbatim (no fuzzy name
   matching: a wrong guess would attribute data to the wrong station). An
   unknown key is provisioned as an inactive placeholder station so the
   foreign keys hold and no row is dropped;
4. hourly (Z-hour) rows go to ``observations``; the whole daily document
   (with its repeated TMAX/TMIN/filas_nuvosidad aux rows) and the monthly
   resumen document are stored VERBATIM in ``summary_logs``;
5. verification: 100%% row-count equality plus a deterministic ~10%%
   field-by-field sample against the source documents.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from oms_core.db.repositories import observations, stations, summaries
from oms_core.db.repositories.observations import Observation
from oms_core.importer import parse, scan
from oms_core.importer.parse import DailyDocument, ParseError, ResumenDocument

#: horarias hora label of a standard synoptic hour (e.g. '06Z', '21Z').
Z_HORA = re.compile(r"^\d{2}Z$")
#: numeric field keys of a standard hourly row (OLD fixture shape).
FIELDS = ("p_est", "p_nmm", "rocio", "t_vapor", "hr", "v_dir_deg", "v_vel")


def _norm_value(value: object) -> float | str | None:
    """Normalise a JSON scalar for comparison against SQLite values.

    SQLite stores NaN as NULL and the legacy corpus uses NaN where later
    files use null, so both sides normalise to None.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return str(value)


@dataclass(frozen=True)
class FileResult:
    path: str
    kind: str
    sha256: str
    status: str  # "imported" | "error"
    detail: str = ""


@dataclass
class ImportReport:
    files: list[FileResult] = field(default_factory=list)
    stations_provisioned: list[str] = field(default_factory=list)
    row_counts: dict[str, tuple[int, int]] = field(default_factory=dict)
    sample_comparisons: int = 0
    sample_mismatches: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    #: keys already in the DB from earlier runs, outside this run's corpus
    preexisting_keys: int = 0

    @property
    def ok(self) -> bool:
        counts_equal = all(expected == actual for expected, actual in self.row_counts.values())
        return not self.errors and counts_equal and not self.sample_mismatches

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "files": [vars(f) for f in self.files],
            "stations_provisioned": list(self.stations_provisioned),
            "row_counts": {k: list(v) for k, v in self.row_counts.items()},
            "sample_comparisons": self.sample_comparisons,
            "sample_mismatches": list(self.sample_mismatches),
            "errors": list(self.errors),
            "preexisting_keys": self.preexisting_keys,
        }


@dataclass
class _Parsed:
    source: scan.SourceFile
    raw_text: str
    daily: DailyDocument | None = None
    resumen: ResumenDocument | None = None


class Importer:
    """One-shot, idempotent JSON-to-SQLite importer over a base directory."""

    def __init__(self, conn: sqlite3.Connection, *, sample_rate: float = 0.1) -> None:
        self._conn = conn
        self._sample_rate = sample_rate

    # -- entry point -------------------------------------------------------

    @staticmethod
    def parse_meta(doc: object) -> dict:
        """Expose meta validation (stage-tagged ParseError on bad input)."""
        return parse.parse_meta(doc)

    def import_root(self, root: Path) -> ImportReport:
        report = ImportReport()
        parsed: list[_Parsed] = []

        for source in scan.scan_root(root):
            try:
                parsed.append(self._parse_source(source))
            except (ParseError, OSError, ValueError) as exc:
                detail = f"stage=parse kind={source.kind} path={source.path} detail={exc}"
                report.files.append(
                    FileResult(
                        path=str(source.path),
                        kind=source.kind,
                        sha256=source.sha256,
                        status="error",
                        detail=detail,
                    )
                )
                report.errors.append(detail)

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            for item in parsed:
                self._import_parsed(item, report)
            self._verify(parsed, report)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return report

    # -- parsing -----------------------------------------------------------

    def _parse_source(self, source: scan.SourceFile) -> _Parsed:
        raw = source.path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        item = _Parsed(source=source, raw_text=raw.decode("utf-8"))
        if source.kind == "diario":
            item.daily = parse.parse_daily(doc)
        else:
            item.resumen = parse.parse_resumen(doc)
        return item

    # -- transactional upserts ---------------------------------------------

    def _ensure_station(self, station_key: str, report: ImportReport) -> None:
        if stations.station_exists(self._conn, station_key):
            return
        # Verbatim placeholder (inactive): the foreign keys keep holding and
        # no legacy row is dropped. Completing it is admin work (F3).
        self._conn.execute(
            "INSERT INTO stations (id, name, provincia, latitud, longitud, elevacion, ch, is_active)"
            " VALUES (?, ?, '', 0.0, 0.0, 0.0, 0.0, 0)",
            (station_key, station_key),
        )
        report.stations_provisioned.append(station_key)

    def _import_parsed(self, item: _Parsed, report: ImportReport) -> None:
        source = item.source
        if item.daily is not None:
            daily = item.daily
            self._ensure_station(daily.station, report)
            for row in daily.horarias:
                if not Z_HORA.match(row.hora):
                    continue  # aux rows live in the verbatim daily document
                observations.upsert_observation(
                    self._conn,
                    Observation(
                        station_id=daily.station,
                        fecha=daily.fecha_iso,
                        hora=row.hora,
                        **{key: _norm_value(row.datos.get(key)) for key in FIELDS},
                        observador=row.observador,
                        source_sha256=source.sha256,
                    ),
                )
            summaries.upsert_summary_doc(
                self._conn,
                station_id=daily.station,
                year=int(daily.fecha_iso[0:4]),
                month=int(daily.fecha_iso[5:7]),
                day=int(daily.fecha_iso[8:10]),
                kind="diario",
                data=item.raw_text,
                sha256=source.sha256,
            )
        else:
            resumen = item.resumen
            assert resumen is not None
            self._ensure_station(resumen.station, report)
            summaries.upsert_summary_doc(
                self._conn,
                station_id=resumen.station,
                year=resumen.year,
                month=resumen.month,
                day=0,
                kind="resumen",
                data=item.raw_text,
                sha256=source.sha256,
            )
        report.files.append(
            FileResult(
                path=str(source.path),
                kind=source.kind,
                sha256=source.sha256,
                status="imported",
            )
        )

    # -- §6.3 verification --------------------------------------------------

    def _verify(self, parsed: list[_Parsed], report: ImportReport) -> None:
        self._verify_row_counts(parsed, report)
        self._verify_sample(parsed, report)

    def _verify_row_counts(self, parsed: list[_Parsed], report: ImportReport) -> None:
        """100%% row-count verification, scoped to THIS run's corpus.

        A legacy corpus may contain the same natural key twice (e.g. the
        same day saved under two spellings of the station directory);
        idempotent upserts converge them, so "100% of rows" means every
        distinct natural key of the corpus is present in the DB. Keys in the
        DB from earlier runs over other roots are counted as pre-existing
        (informational), never as failures.
        """
        expected_obs: set[tuple[str, str, str]] = set()
        expected_docs: set[tuple[str, int, int, str, int]] = set()
        for item in parsed:
            if item.daily is not None:
                daily = item.daily
                year, month, day = (
                    int(daily.fecha_iso[0:4]),
                    int(daily.fecha_iso[5:7]),
                    int(daily.fecha_iso[8:10]),
                )
                expected_docs.add((daily.station, year, month, "diario", day))
                for row in daily.horarias:
                    if Z_HORA.match(row.hora):
                        expected_obs.add((daily.station, daily.fecha_iso, row.hora))
            else:
                resumen = item.resumen
                assert resumen is not None
                expected_docs.add((resumen.station, resumen.year, resumen.month, "resumen", 0))

        db_keys = {
            (r[0], r[1], r[2])
            for r in self._conn.execute("SELECT station_id, fecha, hora FROM observations")
        }
        db_docs = {
            (r[0], int(r[1]), int(r[2]), r[3], int(r[4]))
            for r in self._conn.execute(
                "SELECT station_id, year, month, kind, day FROM summary_logs"
            )
        }

        report.preexisting_keys += len(db_keys - expected_obs) + len(db_docs - expected_docs)
        report.row_counts["observations"] = (len(expected_obs), len(expected_obs & db_keys))
        report.row_counts["summary_docs"] = (len(expected_docs), len(expected_docs & db_docs))
        # Missing rows and docs are data loss: hard failure.
        for key in sorted(expected_obs - db_keys):
            report.sample_mismatches.append(f"missing observation row: {key}")
        for key in sorted(expected_docs - db_docs):
            report.sample_mismatches.append(f"missing summary doc: {key}")

    def _sample_indices(self, total: int) -> int:
        """Number of items for a ~{rate:.0%} deterministic sample."""
        return max(1, round(total * self._sample_rate))

    def _pick(self, keys: list, total: int) -> list:
        count = self._sample_indices(total)
        step = max(1, total // count)
        return keys[::step][:count]

    def _verify_sample(self, parsed: list[_Parsed], report: ImportReport) -> None:
        """Deterministic ~10% field-by-field sample (§6.3)."""
        # Only this run's keys are sampled (earlier-run keys belong to
        # another report).
        obs_keys = sorted(
            (r[0], r[1], r[2])
            for r in self._conn.execute("SELECT station_id, fecha, hora FROM observations")
        )
        run_obs = set()
        for item in parsed:
            if item.daily is not None:
                daily = item.daily
                for row in daily.horarias:
                    if Z_HORA.match(row.hora):
                        run_obs.add((daily.station, daily.fecha_iso, row.hora))
        sampled_obs = self._pick([k for k in obs_keys if k in run_obs], len(run_obs))

        by_doc: dict[tuple[str, str], DailyDocument] = {}
        sha_by_doc: dict[tuple[str, str], str] = {}
        for item in parsed:
            if item.daily is not None:
                by_doc[(item.daily.station, item.daily.fecha_iso)] = item.daily
                sha_by_doc[(item.daily.station, item.daily.fecha_iso)] = item.source.sha256

        for station_id, fecha, hora in sampled_obs:
            row = next(
                (
                    r
                    for r in observations.get_day(self._conn, station_id, fecha)
                    if r.hora == hora
                ),
                None,
            )
            daily = by_doc.get((station_id, fecha))
            if row is None or daily is None:
                report.sample_mismatches.append(
                    f"sample: row {station_id}/{fecha}/{hora} disappeared"
                )
                continue
            source_row = next((r for r in daily.horarias if r.hora == hora), None)
            if source_row is None:
                report.sample_mismatches.append(
                    f"sample: {station_id}/{fecha}/{hora} missing from source"
                )
                continue
            report.sample_comparisons += 1
            for key in FIELDS:
                expected = _norm_value(source_row.datos.get(key))
                got = getattr(row, key)
                if expected != got:
                    report.sample_mismatches.append(
                        f"sample {station_id}/{fecha}/{hora}/{key}:"
                        f" expected {expected!r}, got {got!r}"
                    )
            if row.observador != source_row.observador:
                report.sample_mismatches.append(
                    f"sample {station_id}/{fecha}/{hora}/observador:"
                    f" expected {source_row.observador!r}, got {row.observador!r}"
                )
            if row.source_sha256 != sha_by_doc.get((station_id, fecha)):
                report.sample_mismatches.append(
                    f"sample {station_id}/{fecha}/{hora}/source_sha256 mismatch"
                )

        # Sample the verbatim documents too: stored text must be byte-identical.
        run_docs: set[tuple[str, int, int, str, int]] = set()
        for item in parsed:
            if item.daily is not None:
                d = item.daily
                run_docs.add(
                    (d.station, int(d.fecha_iso[0:4]), int(d.fecha_iso[5:7]), "diario",
                     int(d.fecha_iso[8:10]))
                )
            else:
                r = item.resumen
                assert r is not None
                run_docs.add((r.station, r.year, r.month, "resumen", 0))
        docs = sorted(
            (r[0], int(r[1]), int(r[2]), r[3], int(r[4]))
            for r in self._conn.execute(
                "SELECT station_id, year, month, kind, day FROM summary_logs"
            )
        )
        docs = [k for k in docs if k in run_docs]
        raw_by_doc: dict[tuple[str, int, int, str, int], str] = {}
        for item in parsed:
            if item.daily is not None:
                d = item.daily
                raw_by_doc[
                    (d.station, int(d.fecha_iso[0:4]), int(d.fecha_iso[5:7]), "diario",
                     int(d.fecha_iso[8:10]))
                ] = item.raw_text
            else:
                r = item.resumen
                assert r is not None
                raw_by_doc[(r.station, r.year, r.month, "resumen", 0)] = item.raw_text

        for key in self._pick(docs, len(docs)):
            report.sample_comparisons += 1
            stored = summaries.get_summary_doc(
                self._conn, key[0], key[1], key[2], key[3], day=key[4]
            )
            expected = raw_by_doc.get(key)
            if stored != expected:
                report.sample_mismatches.append(f"sample doc {key}: content differs")
