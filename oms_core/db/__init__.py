"""SQLite data core for Neo Arca (PRD F1, ADR-02).

This package owns the schema, the numbered migrations and the per-entity
repositories. It is pure Python (ADR-03: no Qt imports) and uses only the
standard library.

Connection contract (mirrors ``OLD .../db.rs::init_db`` per-connection pragmas):
journal_mode=WAL, foreign_keys=ON and a busy_timeout, applied by
:func:`oms_core.db.connection.connect` to every connection.

The database location is always passed as a parameter; there is no Tauri
handle anywhere in the core.

Write-guard equivalence (replaces ``OLD .../write_guard.rs``): the old code
protected JSON documents from lost updates with an O_EXCL lockfile plus an
atomically rewritten file (lock -> read -> mutate -> fsync write). SQLite
gives the same guarantees through the database engine itself:

- serialisation: a single writer at a time (WAL + busy_timeout; wrap
  multi-statement writes in ``BEGIN IMMEDIATE``);
- atomicity: a transaction either fully commits or fully rolls back — there
  is never a half-written document;
- durability: WAL commits are crash-safe, equivalent to the old fsync.

Every repository mutates data inside a single transaction or a single
statement, so the lock-file dance is no longer needed and cannot be forgotten.
"""
