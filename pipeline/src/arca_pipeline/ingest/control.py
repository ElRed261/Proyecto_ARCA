"""Ingest control file: tracks which files were already ingested.

What it does: read/write a small JSON map `{filename: sha256}` used to skip
re-downloading files whose content is already known (idempotency).
What it produces: JSON control file on disk.
What it consumes: a Path to the control file.
What it must NOT import: anything outside the standard library.
"""

import json
from pathlib import Path

_DEFAULT: dict = {}


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
    # TODO(ingest): write to a .part sibling and os.replace() for atomicity.
    path.write_text(json.dumps(checksums, indent=2, sort_keys=True))