"""Tests for the ingest (bronze) layer: control.py (no deps) + drive.py.

drive tests hard-skip via pytest.importorskip("googleapiclient") when the lib is
absent (local run); they run for real in CI where google-api-python-client is a
declared dependency.
"""

import hashlib
import json

import pytest

from arca_pipeline.ingest import control


def _drive_module():
    pytest.importorskip("googleapiclient")
    from arca_pipeline.ingest import drive

    return drive


def test_sha256_file_matches(tmp_path):
    f = tmp_path / "sample.bin"
    payload = b"estacion central 01032026" * 1000
    f.write_bytes(payload)
    assert control.sha256_file(f) == hashlib.sha256(payload).hexdigest()


def test_checksums_roundtrip(tmp_path):
    ctrl = tmp_path / "state" / "checksums.json"
    checksums = {"a.xlsm": "aa", "sub/b.xlsm": "bb"}
    control.save_checksums(ctrl, checksums)
    assert control.load_checksums(ctrl) == checksums


def test_checksums_empty_when_missing(tmp_path):
    assert control.load_checksums(tmp_path / "nope.json") == {}


def test_write_meta(tmp_path):
    control.write_meta(
        tmp_path,
        "estacion_central_01032026.xlsm",
        "Estacion Central.xlsm",
        "deadbeef",
        "2026-03-01T10:00:00Z",
    )
    meta = json.loads(
        (tmp_path / "estacion_central_01032026.xlsm.meta.json").read_text()
    )
    assert set(meta) == {"source_file", "sha256", "ingested_at", "drive_modified_time"}
    assert meta["source_file"] == "Estacion Central.xlsm"
    assert meta["sha256"] == "deadbeef"
    assert meta["drive_modified_time"] == "2026-03-01T10:00:00Z"


def test_should_download_new_file(tmp_path):
    drive = _drive_module()
    meta = {"id": "1", "name": "nuevo.xlsm", "modified_time": "2026-01-01T00:00:00Z"}
    assert drive.should_download(meta, {}, tmp_path) == (True, "nuevo")


def test_should_download_unchanged(tmp_path):
    drive = _drive_module()
    f = tmp_path / "igual.xlsm"
    f.write_bytes(b"data")
    checksums = {"igual.xlsm": hashlib.sha256(b"data").hexdigest()}
    assert drive.should_download({"name": "igual.xlsm"}, checksums, tmp_path) == (
        False,
        "sin cambios",
    )


def test_should_download_changed(tmp_path):
    drive = _drive_module()
    f = tmp_path / "viejo.xlsm"
    f.write_bytes(b"old")
    checksums = {"viejo.xlsm": hashlib.sha256(b"new").hexdigest()}
    assert drive.should_download({"name": "viejo.xlsm"}, checksums, tmp_path) == (
        True,
        "cambió",
    )


def test_download_atomic_writes_file(tmp_path):
    drive = _drive_module()

    class _Request:
        def __init__(self, payload):
            self._payload = payload

        def execute(self):
            return self._payload

    class _FakeFiles:
        def __init__(self):
            self.get = lambda **kw: _Request({"name": "libro.xlsm"})
            self.get_media = lambda **kw: _Request(b"RAW-XLSM-BYTES")

    class _FakeService:
        def files(self):
            return _FakeFiles()

    out = drive.download_atomic(_FakeService(), "file123", tmp_path)
    assert out == tmp_path / "libro.xlsm"
    assert out.read_bytes() == b"RAW-XLSM-BYTES"
    assert not list(tmp_path.glob("*.part"))


def test_download_atomic_cleans_part_on_error(tmp_path):
    drive = _drive_module()

    class _Request:
        def execute(self):
            return {"name": "roto.xlsm"}

    class _BoomMedia:
        def execute(self):
            raise OSError("network down")

    class _FakeFiles:
        def __init__(self):
            self.get = lambda **kw: _Request()

        def get_media(self, **kw):
            return _BoomMedia()

    class _FakeService:
        def files(self):
            return _FakeFiles()

    with pytest.raises(OSError):
        drive.download_atomic(_FakeService(), "file123", tmp_path)
    assert not list(tmp_path.glob("*.part"))
