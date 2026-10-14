"""Shared pytest helpers for the Neo Arca test suite.

Makes the repository root importable (tests/ is not a package) and provides
database helpers shared by the F1 test modules.
"""

import os
import sys
from pathlib import Path

# Qt tests must never open a window: force the offscreen platform before any
# QApplication can exist (pytest-qt creates one lazily).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from oms_core.db import migrations
from oms_core.db.connection import connect

FIXTURES = Path(__file__).resolve().parent / "fixtures"
IMPORTER_FIXTURES = FIXTURES / "importer"


@pytest.fixture()
def fresh_db(tmp_path):
    """Open a WAL connection and migrate it to the latest version."""
    conn = connect(tmp_path / "test.db")
    migrations.migrate(conn)
    yield conn
    conn.close()
