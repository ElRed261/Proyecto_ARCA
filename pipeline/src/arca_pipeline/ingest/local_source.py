"""Local-filesystem boundary of the ingest layer (Drive stand-in).

What it does: lists spreadsheet files under a local directory tree and copies
them atomically into raw/ so the pipeline can run without any Google Drive
connection.
What it produces: file metadata dicts and local raw files on disk.
What it consumes: a directory tree of .xlsm/.xlsx files and the control file's
known checksums.
What it must NOT import: transform/validate/load modules or anything UI-related.

Layer frontier: this is the ONLY module allowed to read the external source
tree; Google Drive remains isolated in drive.py.
"""

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

_EXCEL_EXTS = (".xlsm", ".xlsx")


def _flat_name(rel: Path) -> str:
    """Unique flat name for raw/: 'MDCY/2026/Abril/MDCY 01042026.xlsm' ->
    'MDCY__2026__Abril__MDCY 01042026.xlsm' (source trees nest by station/year)."""
    return "__".join(rel.parts)


def list_new_files(root: Path, known_checksums: dict[str, str]) -> list[dict]:
    """List `.xlsm`/`.xlsx` under `root` recursively.

    Returns dicts shaped exactly like drive.list_new_files output:
    {"id": absolute path, "name": flat unique name, "modified_time": mtime ISO}.
    Like the Drive backend, `known_checksums` is accepted for signature parity
    but not used to prune here — content freshness is decided by
    should_download against the local raw copy.
    """
    metas: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _EXCEL_EXTS:
            continue
        rel = path.relative_to(root)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        metas.append(
            {
                "id": str(path.resolve()),
                "name": _flat_name(rel),
                "modified_time": mtime,
            }
        )
    return metas


def download_atomic(root: Path, file_id: str, dest_dir: Path) -> Path:
    """Copy the source file into `dest_dir` as `<name>.part`, rename to <name>.

    Atomic rename guarantees the final path only ever contains a complete file.
    On any error the leftover `.part` is removed. Returns the final Path.
    """
    name = _flat_name(Path(file_id).relative_to(root))
    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest_dir / f"{name}.part"
    final = dest_dir / name
    try:
        shutil.copyfile(file_id, part)
        os.replace(part, final)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return final
