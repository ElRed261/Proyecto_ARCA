"""JSON legacy -> SQLite importer (PRD F1, §6.3).

One-shot, re-runnable (idempotent) import of the legacy JSON corpus into
SQLite. The JSON side becomes read-only legacy data (ADR-02)."""

from oms_core.importer.importer import FileResult, Importer, ImportReport

__all__ = ["FileResult", "ImportReport", "Importer"]
