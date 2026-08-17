"""Google Drive boundary of the ingest layer.

What it does: lists files younger than the known checksums and downloads them
atomically (temp .part file, rename on success) so a crash never leaves a
half-written raw file.
What it produces: file metadata dicts and local raw files on disk.
What it consumes: Google Drive API (service account credentials from config),
a local control file (see control.py) with known checksums.
What it must NOT import: transform/validate/load modules or anything UI-related.

Layer frontier: this is the ONLY module allowed to talk to Google Drive.
"""

from pathlib import Path

import googleapiclient.discovery  # noqa: F401  # reserved, used when implemented


def list_new_files(folder_id: str, known_checksums: dict) -> list[dict]:
    """List files in `folder_id` whose sha256 is not in `known_checksums`.

    Returns list of dicts, each with at least:
    {"file_id": str, "name": str, "modified_time": str, "size": int}.
    """
    # TODO(ingest): connect with service account, walk folder, compare checksums.
    raise NotImplementedError


def download_atomic(file_id: str, dest_dir: Path) -> Path:
    """Download file `file_id` to `dest_dir` as `<name>.part`, then rename to `name`.

    Atomic rename guarantees the final path only ever contains a complete file.
    Returns the final Path.
    """
    # TODO(ingest): stream download via the Drive API media endpoint; fsync before rename.
    raise NotImplementedError