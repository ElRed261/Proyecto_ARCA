"""F1 importer: scan both directory layouts and month namings, idempotent
upserts, SHA-256 per source file, and the §6.3 verification report
(100% row counts + 10% field-by-field sample).

Fixture data (tests/fixtures/importer) comes from the OLD sample corpus:
- 'Estacion Central/2025/05/' (non-accented station dir, zero-padded month)
- 'Estación Central/2025/05/' (accented station dir, zero-padded month)
- 'MDJB/2025/6/'              (unpadded month dir — the other month naming)
- 'resumen/resumen_78485_102025.json' (monthly summary, {meta, datos} shape)
"""

import json
import sqlite3
from pathlib import Path

import pytest

from oms_core.db import migrations
from oms_core.db.connection import connect
from oms_core.db.repositories import observations, summaries
from oms_core.importer import Importer, scan
from oms_core.importer.parse import ParseError

IMPORTER_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "importer"


def _db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "import.db")
    migrations.migrate(conn)
    return conn


# --------------------------------------------------------------------------
# scan
# --------------------------------------------------------------------------


def test_scan_finds_both_layouts_and_month_namings():
    sources = scan.scan_root(IMPORTER_FIXTURES)
    by_name = {s.path.name: s for s in sources}
    assert set(by_name) == {
        "Estacion Central 07052025.json",
        "Estación Central 15052025.json",
        "MDJB 08062025.json",
        "resumen_78485_102025.json",
    }
    assert by_name["MDJB 08062025.json"].kind == "diario"
    assert by_name["MDJB 08062025.json"].day == 8
    assert by_name["MDJB 08062025.json"].month == 6
    assert by_name["MDJB 08062025.json"].year == 2025
    assert by_name["resumen_78485_102025.json"].kind == "resumen"
    assert by_name["resumen_78485_102025.json"].month == 10
    # every scanned file carries its SHA-256
    assert all(len(s.sha256) == 64 for s in sources)


# --------------------------------------------------------------------------
# full import over the fixture corpus
# --------------------------------------------------------------------------


def test_import_fixtures_report_counts(tmp_path):
    conn = _db(tmp_path)
    report = Importer(conn).import_root(IMPORTER_FIXTURES)

    # 24 hourly rows (8 Z-hours x 3 daily files), 4 docs (3 diario + 1 resumen)
    assert report.row_counts["observations"] == (24, 24)
    assert report.row_counts["summary_docs"] == (4, 4)
    assert report.ok
    assert report.errors == []
    assert sorted(report.stations_provisioned) == [
        "Estacion Central",
        "Estación Central",
        "MDJB",
    ]
    # 10% sample actually compared, field by field, with zero mismatches
    assert report.sample_comparisons >= 2
    assert report.sample_mismatches == []
    assert len(report.files) == 4
    assert all(len(f.sha256) == 64 for f in report.files)
    conn.close()


def test_imported_observation_values_match_source(tmp_path):
    conn = _db(tmp_path)
    Importer(conn).import_root(IMPORTER_FIXTURES)
    rows = observations.get_day(conn, "MDJB", "2025-06-08")
    by_hora = {r.hora: r for r in rows}
    assert sorted(by_hora) == ["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"]
    assert by_hora["12Z"].p_est == 1014.1
    assert by_hora["12Z"].p_nmm == 1017.6
    assert by_hora["15Z"].v_dir_deg == 90
    assert by_hora["15Z"].v_vel == 3.1
    # missing hour rows in the source stay absent; null fields stay null
    assert by_hora["06Z"].p_est is None
    conn.close()


def test_aux_rows_live_in_verbatim_daily_doc_not_observations(tmp_path):
    """TMAX/TMIN/filas_nuvosidad repeat within one file; the doc keeps them
    verbatim in summary_logs (kind='diario'), observations stays unique by
    (station, fecha, hora)."""
    conn = _db(tmp_path)
    Importer(conn).import_root(IMPORTER_FIXTURES)
    assert conn.execute(
        "SELECT COUNT(*) FROM observations WHERE hora LIKE 'T%' OR hora LIKE 'filas%'"
    ).fetchone()[0] == 0
    doc = summaries.get_summary_doc(conn, "MDJB", 2025, 6, "diario", day=8)
    raw = (IMPORTER_FIXTURES / "json/MDJB/2025/6/MDJB 08062025.json").read_text(encoding="utf-8")
    assert doc == raw  # verbatim
    parsed = json.loads(doc)
    assert [h["hora"] for h in parsed["horarias"]].count("TMAX") == 3
    conn.close()


def test_import_resumen_doc_verbatim(tmp_path):
    conn = _db(tmp_path)
    Importer(conn).import_root(IMPORTER_FIXTURES)
    doc = summaries.get_summary_doc(conn, "78485", 2025, 10, "resumen")
    raw = (IMPORTER_FIXTURES / "resumen/resumen_78485_102025.json").read_text(encoding="utf-8")
    assert doc == raw
    parsed = json.loads(doc)
    assert parsed["meta"]["estacion"] == "78485"
    assert len(parsed["datos"]) == 30
    # 78485 is a seeded station: no placeholder must be created for it
    assert "78485" not in [s["id"] for s in _provisioned(conn)]
    conn.close()


def _provisioned(conn):
    return [
        {"id": r[0], "is_active": r[1]}
        for r in conn.execute(
            "SELECT id, is_active FROM stations WHERE id NOT IN "
            "('78451','MDCY','78457','78482','78467','78464','78486','78485',"
            "'78479','78484','78466','78480','78473','78488','78460')"
        )
    ]


def test_provisioned_stations_are_inactive_placeholders(tmp_path):
    conn = _db(tmp_path)
    Importer(conn).import_root(IMPORTER_FIXTURES)
    provisioned = _provisioned(conn)
    assert {p["id"] for p in provisioned} == {
        "Estacion Central",
        "Estación Central",
        "MDJB",
    }
    assert all(p["is_active"] == 0 for p in provisioned)
    conn.close()


# --------------------------------------------------------------------------
# idempotency: import twice
# --------------------------------------------------------------------------


def test_sequential_imports_over_disjoint_roots_are_independent(tmp_path):
    """Importing a second root must not flag the first run's rows as failures:
    row-count verification is scoped to each run's own corpus."""
    conn = _db(tmp_path)
    first = Importer(conn).import_root(IMPORTER_FIXTURES / "resumen")
    assert first.ok
    assert first.row_counts["summary_docs"] == (1, 1)
    assert first.preexisting_keys == 0

    second = Importer(conn).import_root(IMPORTER_FIXTURES / "json")

    assert second.ok
    assert second.row_counts["observations"] == (24, 24)
    assert second.row_counts["summary_docs"] == (3, 3)
    # the single resumen doc imported before is pre-existing, not an error
    assert second.preexisting_keys == 1
    assert second.sample_mismatches == []
    conn.close()


def test_import_twice_is_idempotent(tmp_path):
    conn = _db(tmp_path)
    first = Importer(conn).import_root(IMPORTER_FIXTURES)
    obs_after_first = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    docs_after_first = conn.execute("SELECT COUNT(*) FROM summary_logs").fetchone()[0]
    stations_after_first = conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]

    second = Importer(conn).import_root(IMPORTER_FIXTURES)

    assert second.ok
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == obs_after_first
    assert conn.execute("SELECT COUNT(*) FROM summary_logs").fetchone()[0] == docs_after_first
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == stations_after_first
    assert second.row_counts == first.row_counts
    assert second.sample_mismatches == []
    conn.close()


# --------------------------------------------------------------------------
# loud failure on broken input
# --------------------------------------------------------------------------


def test_broken_file_is_reported_and_others_still_import(tmp_path):
    """A file matching the daily layout but with corrupt content is reported
    loudly; non-matching *.json names (other modules share the base dir) are
    outside the corpus and ignored."""
    conn = _db(tmp_path)
    broken = tmp_path / "broken.json"
    broken.write_text("{no es json", encoding="utf-8")  # scanned out: no layout match
    good_dir = tmp_path / "MDJB" / "2025" / "7"
    good_dir.mkdir(parents=True)
    daily = good_dir / "MDJB 09072025.json"
    daily.write_text("{no es json", encoding="utf-8")  # matches: must fail loudly
    good = good_dir / "MDJB 10072025.json"
    sample = IMPORTER_FIXTURES / "json/MDJB/2025/6/MDJB 08062025.json"
    good.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")

    report = Importer(conn).import_root(tmp_path)

    assert not report.ok
    assert [Path(f.path).name for f in report.files if f.status == "error"] == [
        "MDJB 09072025.json"
    ]
    assert report.errors and "stage=parse" in report.errors[0]
    assert report.row_counts["observations"] == (8, 8)
    assert report.row_counts["summary_docs"] == (1, 1)
    conn.close()


def test_invalid_calendar_date_rejected(tmp_path):
    conn = _db(tmp_path)
    bad = tmp_path / "MDJB" / "2025" / "2"
    bad.mkdir(parents=True)
    doc = {
        "meta": {"estacion": "MDJB", "fecha": "30022025"},
        "horarias": [{"hora": "06Z", "datos": {"p_est": 1.0}, "observador": ""}],
        "resumen_dia": {"pp": None},
    }
    (bad / "MDJB 30022025.json").write_text(json.dumps(doc), encoding="utf-8")

    report = Importer(conn).import_root(tmp_path)

    assert not report.ok
    assert report.row_counts["observations"] == (0, 0)
    # stage + path + detail in every error; the calendar message mirrors
    # json_handler::parse_date_parts (no data row is created).
    assert "stage=parse" in report.errors[0] and "día" in report.errors[0]
    conn.close()


def test_parse_error_message_mentions_stage_path_and_detail():
    with pytest.raises(ParseError) as exc:
        Importer.parse_meta({"estacion": "", "fecha": "01012025"})
    assert "meta" in str(exc.value)


# --------------------------------------------------------------------------
# SHA-256 recorded per row
# --------------------------------------------------------------------------


def test_observation_rows_carry_source_sha256(tmp_path):
    conn = _db(tmp_path)
    Importer(conn).import_root(IMPORTER_FIXTURES)
    raw = (IMPORTER_FIXTURES / "json/MDJB/2025/6/MDJB 08062025.json").read_bytes()
    import hashlib

    expected = hashlib.sha256(raw).hexdigest()
    rows = observations.get_day(conn, "MDJB", "2025-06-08")
    assert all(r.source_sha256 == expected for r in rows)
    conn.close()
