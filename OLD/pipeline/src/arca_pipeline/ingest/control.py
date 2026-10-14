"""Ingest control file: tracks which files were already ingested.

What it does: read/write a small JSON map `{filename: sha256}` used to skip
re-downloading files whose content is already known (idempotency). Also hashes
raw files and writes the bronze `.meta.json` sidecar contract.
What it produces: JSON control file and meta sidecars on disk.
What it consumes: a Path to files/directories.
What it must NOT import: anything outside the standard library.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

_DEFAULT: dict = {}
_CHUNK = 1_000_000


def _atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` via a temp sibling + os.replace (atomic)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text)
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def load_checksums(path: Path) -> dict:
    """Return {filename: sha256} from `path`. Missing/corrupt file -> empty dict."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        # TODO(ingest): corrupt control file — take a backup copy before reset.
        return {**_DEFAULT}


def save_checksums(path: Path, checksums: dict) -> None:
    """Atomically persist `{filename: sha256}` to `path` (write temp, then rename)."""
    _atomic_write_text(path, json.dumps(checksums, indent=2, sort_keys=True))


def sha256_file(path: Path) -> str:
    """Hex sha256 of `path`, computed in 1MB chunks (bounded memory)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def write_meta(
    meta_dir: Path,
    filename: str,
    source_file: str,
    sha256: str,
    drive_modified_time: str,
) -> None:
    """Write the bronze contract sidecar `{filename}.meta.json`.

    payload: {source_file, sha256, ingested_at (UTC ISO), drive_modified_time}.
    """
    meta = {
        "source_file": source_file,
        "sha256": sha256,
        "ingested_at": datetime.now(UTC).isoformat(),
        "drive_modified_time": drive_modified_time,
    }
    _atomic_write_text(meta_dir / f"{filename}.meta.json", json.dumps(meta, indent=2, sort_keys=True))
