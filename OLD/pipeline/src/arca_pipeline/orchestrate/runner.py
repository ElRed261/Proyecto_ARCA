"""Top-level orchestration flow.

What it does: runs one full pipeline pass in order:
    poll source (local tree or Drive) -> download new files -> transform
    -> validate -> load silver -> build gold KPIs.
What it produces: a run-status dict used for observability (last_run.json).
What it consumes: every pipeline layer above plus config.
What it must NOT import: any UI/desktop code.

Prefect @flow wiring: if prefect is installed the same logic runs as a
prefect flow (arca_flow); otherwise the same plain function runs directly —
no extra dependency required. Retries are flow-level (_retry_call), not
per-task.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ponytail: try prefect, fallback to plain functions — no hard dependency
try:
    from prefect import flow  # type: ignore

    _HAS_PREFECT = True
except ImportError:  # pragma: no cover
    _HAS_PREFECT = False

    def flow(_fn=None, **_kw):  # type: ignore
        def decorator(fn):
            return fn

        if _fn is not None:
            return _fn
        return decorator


try:
    from tenacity import retry, stop_after_attempt, wait_exponential  # type: ignore

    _HAS_TENACITY = True
except ImportError:  # pragma: no cover
    _HAS_TENACITY = False
    retry = None  # type: ignore
    stop_after_attempt = None  # type: ignore
    wait_exponential = None  # type: ignore

try:
    from arca_pipeline.config import _PIPELINE_ROOT, settings
except Exception:  # noqa: BLE001  # pragma: no cover # ponytail: fallback when pydantic-settings not installed
    _PIPELINE_ROOT = Path(__file__).resolve().parents[3]

    class _DummySettings:  # ponytail: minimal stub — env vars still work via os.getenv
        drive_folder_id: str = os.getenv("DRIVE_FOLDER_ID", "")
        database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://arca:arca@localhost:5432/arca")
        google_credentials_path: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "")

    settings = _DummySettings()  # type: ignore

from arca_pipeline.ingest import control, drive, local_source
from arca_pipeline.load.gold import build_monthly_kpis
from arca_pipeline.load.silver import upsert_observations
from arca_pipeline.transform.excel_to_json import parse_excel
from arca_pipeline.validate.contracts import validate_day


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _retry_call(fn, *args, max_attempts: int = 3, **kwargs):
    """3-attempt exponential backoff — tenacity if available else simple loop."""
    if _HAS_TENACITY:
        # ponytail: tenacity path — decorator built at call time to keep import soft
        decorated = retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(fn)
        return decorated(*args, **kwargs)
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                raise
            sleep_s = 2**attempt
            logger.warning(
                "retry %s/%s for %s after error: %s (sleep %ss)",
                attempt + 1,
                max_attempts,
                getattr(fn, "__name__", str(fn)),
                exc,
                sleep_s,
            )
            time.sleep(sleep_s)
    raise last_exc  # pragma: no cover


def _resolve_paths(
    raw_dir: Path | None,
    state_path: Path | None,
    rejected_dir: Path | None,
    last_run_path: Path | None,
) -> tuple[Path, Path, Path, Path]:
    raw = Path(raw_dir) if raw_dir is not None else _PIPELINE_ROOT / "data" / "raw"
    state = (
        Path(state_path) if state_path is not None else _PIPELINE_ROOT / "data" / "state" / "checksums.json"
    )
    rejected = (
        Path(rejected_dir) if rejected_dir is not None else _PIPELINE_ROOT / "data" / "rejected"
    )
    last_run = (
        Path(last_run_path)
        if last_run_path is not None
        else _PIPELINE_ROOT / "data" / "state" / "last_run.json"
    )
    return raw, state, rejected, last_run


def _build_engine(database_url: str):
    from sqlalchemy import create_engine  # local import — ponytail: no hard dep at import time

    return create_engine(database_url)


def _run_pipeline_impl(
    drive_folder_id: str | None = None,
    database_url: str | None = None,
    raw_dir: Path | str | None = None,
    state_path: Path | str | None = None,
    rejected_dir: Path | str | None = None,
    last_run_path: Path | str | None = None,
    drive_service=None,
    engine=None,
) -> dict:
    started = datetime.now(UTC)
    started_at = started.isoformat()
    logger.info("pipeline started: %s", started_at)

    folder_id = drive_folder_id if drive_folder_id is not None else settings.drive_folder_id
    db_url = database_url if database_url is not None else settings.database_url

    raw_p, state_p, rejected_p, last_run_p = _resolve_paths(
        Path(raw_dir) if isinstance(raw_dir, str) else raw_dir,
        Path(state_path) if isinstance(state_path, str) else state_path,
        Path(rejected_dir) if isinstance(rejected_dir, str) else rejected_dir,
        Path(last_run_path) if isinstance(last_run_path, str) else last_run_path,
    )
    raw_p.mkdir(parents=True, exist_ok=True)
    rejected_p.mkdir(parents=True, exist_ok=True)
    state_p.parent.mkdir(parents=True, exist_ok=True)
    last_run_p.parent.mkdir(parents=True, exist_ok=True)

    known = control.load_checksums(state_p)

    # build drive service if not injected and credentials available
    svc = drive_service
    if svc is None and folder_id:
        creds = settings.google_credentials_path
        if creds and Path(creds).exists():
            try:
                svc = drive.build_service(creds)
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to build drive service: %s", exc)
                svc = None
        else:
            logger.info("no drive service injected and no credentials — listing will be skipped if not mocked")

    files: list[dict] = []
    # local source mode: ingest from a filesystem tree, no Drive connection
    source_root = Path(settings.source_dir) if settings.source_dir else None
    if source_root is not None:
        if not source_root.is_dir():
            logger.warning("source_dir %s is not a directory — no files to ingest", source_root)
        else:
            try:
                files = local_source.list_new_files(source_root, known)
                logger.info("listed %s files from local source %s", len(files), source_root)
            except Exception as exc:  # noqa: BLE001
                logger.warning("local list_new_files failed: %s", exc)
                files = []
    elif svc is not None and folder_id:
        try:
            files = drive.list_new_files(svc, folder_id, known)
            logger.info("listed %s files from Drive folder %s", len(files), folder_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("list_new_files failed: %s", exc)
            files = []
    else:
        # when svc is mocked in tests, list_new_files is patched so this branch
        # still works via the mock; if not mocked and no svc/folder, leave files empty
        if svc is None:
            logger.info("no drive service/folder_id — no files to ingest")
        files = []

    files_ingested = 0
    files_rejected = 0
    rows_loaded = 0
    affected: set[tuple[str, int, int]] = set()

    # lazy engine — only create when first upsert needed
    eng = engine

    def _get_engine():
        nonlocal eng
        if eng is not None:
            return eng
        try:
            eng = _build_engine(db_url)
        except Exception as exc:
            raise RuntimeError(f"cannot create database engine for {db_url}: {exc}") from exc
        return eng

    for meta in files:
        name = str(meta.get("name") or meta.get("id") or "unknown")
        file_id = str(meta.get("id") or name)
        modified = str(meta.get("modified_time") or "")

        # ponytail: reuse should_download for idempotency even though list_new_files already lists all
        try:
            need, _reason = drive.should_download(meta, known, raw_p)
        except Exception:  # noqa: BLE001
            need = True
        if not need:
            logger.info("skip unchanged file %s", name)
            continue

        # download with retry
        try:
            if source_root is not None:
                dest: Path = _retry_call(local_source.download_atomic, source_root, file_id, raw_p)
            else:
                dest: Path = _retry_call(drive.download_atomic, svc, file_id, raw_p)
        except Exception as exc:  # noqa: BLE001
            logger.warning("download failed for %s (%s): %s", name, file_id, exc)
            files_rejected += 1
            _atomic_write_json(
                rejected_p / f"{Path(name).name}.rejected.json",
                {"source_file": name, "file_id": file_id, "reason": f"download_error: {exc}"},
            )
            continue

        try:
            sha = control.sha256_file(dest)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sha256 failed for %s: %s", dest, exc)
            sha = ""

        # bronze sidecar
        try:
            control.write_meta(raw_p, dest.name, dest.name, sha, modified)
        except Exception as exc:  # noqa: BLE001
            logger.warning("write_meta failed for %s: %s", dest.name, exc)

        # transform
        try:
            day = parse_excel(dest)
        except Exception as exc:  # noqa: BLE001
            logger.warning("parse_excel failed for %s: %s", dest.name, exc)
            files_rejected += 1
            _atomic_write_json(
                rejected_p / f"{dest.name}.rejected.json",
                {
                    "source_file": dest.name,
                    "sha256": sha,
                    "file_id": file_id,
                    "reason": f"parse_error: {exc}",
                },
            )
            continue

        day["source_sha256"] = sha
        if "validated_at" not in day:
            day["validated_at"] = datetime.now(UTC).isoformat()

        df, errors = validate_day(day)

        if df.empty:
            files_rejected += 1
            reason = "; ".join(errors) if errors else "validation failed (no rows)"
            logger.warning("validation rejected %s: %s", dest.name, reason)
            _atomic_write_json(
                rejected_p / f"{dest.name}.rejected.json",
                {
                    "source_file": dest.name,
                    "sha256": sha,
                    "file_id": file_id,
                    "errors": errors,
                    "reason": reason,
                },
            )
            continue

        if errors:
            logger.warning("partial validation errors for %s: %s", dest.name, "; ".join(errors))

        # load silver with retry
        try:
            e = _get_engine()
            if e is None:
                raise RuntimeError("no engine available")
            count = _retry_call(upsert_observations, e, df)
            # upsert_observations returns rowcount on sqlite/postgres; fallback to len(df)
            if not isinstance(count, int):
                count = len(df)
            # sqlite rowcount may be -1 on some drivers — treat as len(df)
            if count is None or count < 0:
                count = len(df)
            rows_loaded += count
            files_ingested += 1
            for _, row in df.iterrows():
                try:
                    fecha = str(row["fecha"])
                    station = str(row["station_code"])
                    y_str, m_str, _ = fecha.split("-")
                    affected.add((station, int(y_str), int(m_str)))
                except Exception:  # noqa: BLE001, S112
                    continue
            known[dest.name] = sha
            logger.info("ingested %s: %s rows", dest.name, count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("upsert failed for %s: %s", dest.name, exc)
            files_rejected += 1
            _atomic_write_json(
                rejected_p / f"{dest.name}.rejected.json",
                {
                    "source_file": dest.name,
                    "sha256": sha,
                    "file_id": file_id,
                    "errors": errors,
                    "reason": f"load_error: {exc}",
                },
            )
            continue

    # persist checksums
    try:
        control.save_checksums(state_p, known)
    except Exception as exc:  # noqa: BLE001
        logger.warning("save_checksums failed: %s", exc)

    # gold — one upsert per affected month
    if affected and _get_engine() is not None:
        for station_code, year, month in sorted(affected):
            try:
                _retry_call(build_monthly_kpis, _get_engine(), station_code, year, month)
                logger.info("gold built for %s %s-%02d", station_code, year, month)
            except Exception as exc:  # noqa: BLE001
                logger.warning("gold build failed for %s %s-%02d: %s", station_code, year, month, exc)

    finished = datetime.now(UTC)
    finished_at = finished.isoformat()
    duration_s = (finished - started).total_seconds()

    status = {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": duration_s,
        "files_ingested": files_ingested,
        "files_rejected": files_rejected,
        "rows_loaded": rows_loaded,
    }
    # backward compat key used in older docs/tests
    status["rejected"] = files_rejected

    try:
        _atomic_write_json(last_run_p, status)
    except Exception as exc:  # noqa: BLE001
        logger.warning("last_run.json write failed: %s", exc)

    logger.info(
        "pipeline finished: ingested=%s rejected=%s rows=%s duration=%.2fs",
        files_ingested,
        files_rejected,
        rows_loaded,
        duration_s,
    )
    return status


# -- prefect flow -------------------------------------------------------------
# ponytail: one flow wrapper when prefect is present, plain function otherwise

if _HAS_PREFECT:

    @flow(name="arca_flow")
    def arca_flow(  # type: ignore[no-redef]
        drive_folder_id: str | None = None,
        database_url: str | None = None,
        raw_dir: Path | str | None = None,
        state_path: Path | str | None = None,
        rejected_dir: Path | str | None = None,
        last_run_path: Path | str | None = None,
        drive_service=None,
        engine=None,
    ) -> dict:
        return _run_pipeline_impl(
            drive_folder_id=drive_folder_id,
            database_url=database_url,
            raw_dir=raw_dir,
            state_path=state_path,
            rejected_dir=rejected_dir,
            last_run_path=last_run_path,
            drive_service=drive_service,
            engine=engine,
        )

else:  # pragma: no cover

    def arca_flow(  # type: ignore[no-redef]
        drive_folder_id: str | None = None,
        database_url: str | None = None,
        raw_dir: Path | str | None = None,
        state_path: Path | str | None = None,
        rejected_dir: Path | str | None = None,
        last_run_path: Path | str | None = None,
        drive_service=None,
        engine=None,
    ) -> dict:
        return _run_pipeline_impl(
            drive_folder_id=drive_folder_id,
            database_url=database_url,
            raw_dir=raw_dir,
            state_path=state_path,
            rejected_dir=rejected_dir,
            last_run_path=last_run_path,
            drive_service=drive_service,
            engine=engine,
        )


def run_pipeline(
    drive_folder_id: str | None = None,
    database_url: str | None = None,
    raw_dir: Path | str | None = None,
    state_path: Path | str | None = None,
    rejected_dir: Path | str | None = None,
    last_run_path: Path | str | None = None,
    drive_service=None,
    engine=None,
) -> dict:
    """Execute one full batch pass.

    Returns status: {"started_at", "finished_at", "duration_s", "files_ingested", "files_rejected", "rows_loaded"}.
    When prefect is available the same logic runs via arca_flow; otherwise a plain
    retry loop is used (cron-style fallback).
    """
    if _HAS_PREFECT:
        # ponytail: delegate to flow so prefect UI sees one run, but keep plain fallback for tests
        try:
            return arca_flow(
                drive_folder_id=drive_folder_id,
                database_url=database_url,
                raw_dir=raw_dir,
                state_path=state_path,
                rejected_dir=rejected_dir,
                last_run_path=last_run_path,
                drive_service=drive_service,
                engine=engine,
            )
        except Exception:  # noqa: BLE001
            # if prefect flow fails to init (no server), fallback to plain impl
            return _run_pipeline_impl(
                drive_folder_id=drive_folder_id,
                database_url=database_url,
                raw_dir=raw_dir,
                state_path=state_path,
                rejected_dir=rejected_dir,
                last_run_path=last_run_path,
                drive_service=drive_service,
                engine=engine,
            )
    return _run_pipeline_impl(
        drive_folder_id=drive_folder_id,
        database_url=database_url,
        raw_dir=raw_dir,
        state_path=state_path,
        rejected_dir=rejected_dir,
        last_run_path=last_run_path,
        drive_service=drive_service,
        engine=engine,
    )


if __name__ == "__main__":
    import sys

    sys.exit(run_pipeline())
