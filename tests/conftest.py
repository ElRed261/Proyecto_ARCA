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


@pytest.fixture(autouse=True)
def _cheap_bcrypt(monkeypatch):
    """Hash passwords at the bcrypt minimum during tests.

    Production keeps cost 12 (~0.24 s per hash, deliberately slow against
    brute force), but the suite hashed hundreds of passwords and that single
    constant was the whole cost of the auth module. A hash made here still
    verifies normally, so the login paths stay real.
    """
    from oms_core.services import auth

    monkeypatch.setattr(auth, "DEFAULT_BCRYPT_COST", 4, raising=False)


@pytest.fixture()
def fresh_db(tmp_path):
    """Open a WAL connection and migrate it to the latest version."""
    conn = connect(tmp_path / "test.db")
    migrations.migrate(conn)
    yield conn
    conn.close()
