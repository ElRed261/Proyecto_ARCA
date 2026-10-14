"""Per-entity repositories over the migrated schema.

One module per entity, mirroring the OLD Rust layout (db.rs schema +
sqlite_audit_repository.rs audit queries + sync_queue.rs queue helpers).
All functions take an explicit ``sqlite3.Connection`` — no pools, no
globals, no Tauri handle (ADR-03).
"""
