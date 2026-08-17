"""Top-level orchestration flow.

What it does: runs one full pipeline pass in order:
    poll Drive -> download new files -> transform -> validate -> load silver
    -> build gold KPIs -> notify.
What it produces: a run-status dict used for observability (last_run.json).
What it consumes: every pipeline layer above plus config.
What it must NOT import: any UI/desktop code.

The Prefect @flow/@task wiring lands here once the individual steps are
implemented. Today this is a stub so the CLI entry point exists:

    python -m arca_pipeline.orchestrate.runner
"""

from __future__ import annotations


def run_pipeline() -> dict:
    """Execute one full batch pass.

    Returns status: {"files_ingested": int, "rejected": int, "duration_s": float}.
    """
    # TODO(orchestrate): Prefect @flow wrapping:
    #   ingest.list_new_files + download_atomic ... -> transform.parse_excel
    #   -> validate.validate_silver -> load.upsert_observations
    #   -> load.build_monthly_kpis -> notify (Telegram if token set)
    #   -> persist status to last_run.json; secrets from config.settings.
    raise NotImplementedError


if __name__ == "__main__":
    # TODO(orchestrate): read run_interval_hours and deploy a scheduled flow.
    raise SystemExit(run_pipeline())