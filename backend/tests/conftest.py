import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from beacon.adapters.persistence.db import connect, run_migrations

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    """A tmp SQLite file with all real migrations applied."""
    conn = connect(tmp_path / "beacon.db")
    run_migrations(conn, MIGRATIONS_DIR)
    return conn


@pytest.fixture(scope="session")
def load_fixture() -> Callable[[str], Any]:
    def _load(relative_path: str) -> Any:
        return json.loads((FIXTURES_DIR / relative_path).read_text())

    return _load
