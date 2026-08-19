"""Google Drive boundary of the ingest layer.

What it does: lists files under a Drive folder and downloads them atomically
(temp .part file, rename on success) so a crash never leaves a half-written
raw file.
What it produces: file metadata dicts and local raw files on disk.
What it consumes: Google Drive API (service account credentials from config),
a local control file (see control.py) with known checksums.
What it must NOT import: transform/validate/load modules or anything UI-related.

Layer frontier: this is the ONLY module allowed to talk to Google Drive.
"""

import os
from pathlib import Path

import googleapiclient.discovery
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from arca_pipeline.ingest.control import sha256_file

_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
_EXCEL_EXTS = (".xlsm", ".xlsx")


def build_service(credentials_path: str):
    """Build a Drive v3 service from a service-account JSON key file."""
    creds = ServiceAccountCredentials.from_service_account_file(
        credentials_path, scopes=[_SCOPE]
    )
    return googleapiclient.discovery.build("drive", "v3", credentials=creds)


def list_new_files(service, folder_id: str, known_checksums: dict[str, str]) -> list[dict]:
    """List `.xlsm`/`.xlsx` files in `folder_id`, skipping trashed ones.

    Returns list of dicts: {"id", "name", "modified_time"}.
    The sha256 is NOT available from the API — raw metadata is returned and the
    checksum gets computed after download (see should_download). Since content
    freshness is decided there, `known_checksums` is accepted for signature
    stability but not used to prune here.
    """
    response = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name,modifiedTime,mimeType)",
            pageSize=1000,
        )
        .execute()
    )
    return [
        {"id": f["id"], "name": f["name"], "modified_time": f.get("modifiedTime")}
        for f in response.get("files", [])
        if f["name"].lower().endswith(_EXCEL_EXTS)
    ]


def download_atomic(service, file_id: str, dest_dir: Path) -> Path:
    """Download `file_id` to `dest_dir` as `<name>.part`, then rename to <name>.

    Atomic rename guarantees the final path only ever contains a complete file.
    On any error the leftover `.part` is removed. Returns the final Path.
    """
    name = Path(service.files().get(fileId=file_id, fields="name").execute()["name"]).name
    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest_dir / f"{name}.part"
    final = dest_dir / name
    try:
        data = service.files().get_media(fileId=file_id).execute()
        with part.open("wb") as f:
            f.write(data)
        os.replace(part, final)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    return final


# ponytail: no MediaIoBaseDownload — get_media().execute() buffers in memory; swap
# to MediaIoBaseDownload streaming if workbook sizes ever grow past memory budget.
def should_download(file_meta: dict, known_checksums: dict, local_dir: Path) -> tuple[bool, str]:
    """Decide whether `file_meta` needs its content fetched.

    Returns (True, "nuevo") if no local copy, (True, "cambió") if local content
    differs from the known checksum, (False, "sin cambios") if it matches.
    """
    name = Path(file_meta["name"]).name
    local = local_dir / name
    if not local.exists():
        return True, "nuevo"
    if known_checksums.get(name) == sha256_file(local):
        return False, "sin cambios"
    return True, "cambió"
