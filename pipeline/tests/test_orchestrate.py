"""Tests for the orchestrate layer — mocked Drive service."""

import json
from unittest.mock import Mock, patch

from arca_pipeline.orchestrate import runner


def test_run_pipeline_ingests_one_file(tmp_path, fixture_xlsm_path):
    raw = tmp_path / "raw"
    rejected = tmp_path / "rejected"
    state = tmp_path / "state" / "checksums.json"
    last_run = tmp_path / "state" / "last_run.json"
    raw.mkdir(parents=True)
    rejected.mkdir(parents=True)
    state.parent.mkdir(parents=True)

    mock_service = Mock()
    with (
        patch.object(runner.drive, "list_new_files", return_value=[{"id": "abc123", "name": fixture_xlsm_path.name, "modified_time": "2026-03-01T10:00:00Z"}]) as mock_list,
        patch.object(runner.drive, "download_atomic", return_value=fixture_xlsm_path) as mock_dl,
        patch.object(runner.drive, "should_download", return_value=(True, "nuevo")),
        patch.object(runner, "upsert_observations", return_value=2) as mock_upsert,
        patch.object(runner, "build_monthly_kpis", return_value={}) as mock_gold,
    ):
        result = runner.run_pipeline(
            drive_folder_id="test-folder",
            database_url="sqlite:///:memory:",
            raw_dir=raw,
            state_path=state,
            rejected_dir=rejected,
            last_run_path=last_run,
            drive_service=mock_service,
            engine=Mock(),
        )

    assert result["files_ingested"] == 1
    assert result["files_rejected"] == 0
    assert result["rows_loaded"] == 2
    assert result["duration_s"] >= 0
    assert "started_at" in result and "finished_at" in result

    assert last_run.exists()
    data = json.loads(last_run.read_text())
    assert data["files_ingested"] == 1
    assert data["files_rejected"] == 0
    assert data["rows_loaded"] == 2
    assert "started_at" in data
    assert "finished_at" in data
    assert "duration_s" in data

    # no leftover .tmp from atomic write
    assert not list(last_run.parent.glob("*.tmp"))
    assert not list(rejected.glob("*.rejected.json"))

    mock_list.assert_called_once()
    mock_dl.assert_called_once_with(mock_service, "abc123", raw)
    mock_upsert.assert_called_once()
    mock_gold.assert_called_once()
    # gold should be called for station 78486 / 2026-03 (from fixture)
    args = mock_gold.call_args[0]
    assert args[1] == "78486"
    assert args[2] == 2026
    assert args[3] == 3


def test_run_pipeline_rejects_invalid_file(tmp_path):
    raw = tmp_path / "raw"
    rejected = tmp_path / "rejected"
    state = tmp_path / "state" / "checksums.json"
    last_run = tmp_path / "state" / "last_run.json"
    raw.mkdir(parents=True)
    rejected.mkdir(parents=True)
    state.parent.mkdir(parents=True)

    bad = tmp_path / "corrupt.xlsm"
    bad.write_bytes(b"not a real workbook")

    mock_service = Mock()
    with (
        patch.object(runner.drive, "list_new_files", return_value=[{"id": "bad1", "name": bad.name, "modified_time": "2026-03-01T10:00:00Z"}]),
        patch.object(runner.drive, "download_atomic", return_value=bad),
        patch.object(runner.drive, "should_download", return_value=(True, "nuevo")),
        patch.object(runner, "upsert_observations", return_value=1) as mock_upsert,
        patch.object(runner, "build_monthly_kpis") as mock_gold,
    ):
        result = runner.run_pipeline(
            drive_folder_id="test-folder",
            database_url="sqlite:///:memory:",
            raw_dir=raw,
            state_path=state,
            rejected_dir=rejected,
            last_run_path=last_run,
            drive_service=mock_service,
            engine=Mock(),
        )

    assert result["files_ingested"] == 0
    assert result["files_rejected"] == 1
    assert result["rows_loaded"] == 0

    assert last_run.exists()
    data = json.loads(last_run.read_text())
    assert data["files_rejected"] == 1

    rejected_files = list(rejected.glob("*.rejected.json"))
    assert len(rejected_files) == 1
    payload = json.loads(rejected_files[0].read_text())
    assert "reason" in payload
    assert "parse_error" in payload["reason"]

    mock_upsert.assert_not_called()
    mock_gold.assert_not_called()


def test_run_pipeline_retry_and_gold_skipped_when_no_files(tmp_path):
    raw = tmp_path / "raw"
    rejected = tmp_path / "rejected"
    state = tmp_path / "state" / "checksums.json"
    last_run = tmp_path / "state" / "last_run.json"
    raw.mkdir(parents=True)
    rejected.mkdir(parents=True)
    state.parent.mkdir(parents=True)

    mock_service = Mock()
    with (
        patch.object(runner.drive, "list_new_files", return_value=[]),
        patch.object(runner, "upsert_observations") as mock_upsert,
        patch.object(runner, "build_monthly_kpis") as mock_gold,
    ):
        result = runner.run_pipeline(
            drive_folder_id="test-folder",
            database_url="sqlite:///:memory:",
            raw_dir=raw,
            state_path=state,
            rejected_dir=rejected,
            last_run_path=last_run,
            drive_service=mock_service,
            engine=Mock(),
        )

    assert result["files_ingested"] == 0
    assert result["files_rejected"] == 0
    assert result["rows_loaded"] == 0
    assert last_run.exists()
    mock_upsert.assert_not_called()
    mock_gold.assert_not_called()
