"""Tests for the local file source (Drive stand-in)."""

from pathlib import Path

from arca_pipeline.ingest import local_source


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    sub = root / "MDCY" / "2026" / "Abril"
    sub.mkdir(parents=True)
    (sub / "MDCY 01042026.xlsm").write_bytes(b"a" * 128)
    (root / "notes.txt").write_text("not a spreadsheet")
    other = root / "SANTO" / "2026"
    other.mkdir(parents=True)
    (other / "SANTO 02042026.xlsx").write_bytes(b"b" * 64)
    return root


def test_list_picks_only_spreadsheets_recursively(tmp_path):
    root = _tree(tmp_path)

    metas = local_source.list_new_files(root, {})

    names = [m["name"] for m in metas]
    assert names == [
        "MDCY__2026__Abril__MDCY 01042026.xlsm",
        "SANTO__2026__SANTO 02042026.xlsx",
    ]
    assert all(m["id"] and m["modified_time"] for m in metas)


def test_download_atomic_copies_content(tmp_path):
    root = _tree(tmp_path)
    metas = local_source.list_new_files(root, {})
    dest_dir = tmp_path / "raw"

    outs = [local_source.download_atomic(root, m["id"], dest_dir) for m in metas]

    assert all(o.exists() for o in outs)
    assert (dest_dir / "MDCY__2026__Abril__MDCY 01042026.xlsm").read_bytes() == b"a" * 128
    assert (dest_dir / "SANTO__2026__SANTO 02042026.xlsx").read_bytes() == b"b" * 64
