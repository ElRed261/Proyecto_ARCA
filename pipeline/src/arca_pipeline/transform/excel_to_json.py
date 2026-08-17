"""Core transform: .xlsm workbook -> JSON observation dict.

What it does: parses one meteorological Excel file into a portable JSON
payload. PURE core — no file dialogs, no tkinter, no I/O beyond the Path it
receives. Currently a stub: the real parser lives in
miscelaneos/scratch/excel_to_json.py and will be extracted here.
What it produces: one JSON-serializable dict per file.
What it consumes: an .xlsm (or other raw excel extension, see Z_HOUR sheet logic).
What it must NOT import: anything from ingest/validate/load, tkinter, or the UI.

Output contract:
{
  "schema_version": 1,
  "station_code": "3074",
  "fecha": "YYYY-MM-DD",
  "horas": [
    {"hora": "00Z", "temp": ..., "humidity": ..., ...WMO fields...},
    ...
  ]
}
"""

from pathlib import Path


def parse_excel(path: Path) -> dict:
    """Parse the workbook at `path` into the JSON contract described above.

    Raises ValueError for unsupported/malformed files.
    """
    # TODO(transform): extract the core from miscelaneos/scratch/excel_to_json.py:
    #   - drop tkinter/filedialog logic
    #   - build the hours list from the Z-hour sheets (0000Z..2100Z)
    #   - merge multiple files sharing the same fecha, as scratch does
    raise NotImplementedError