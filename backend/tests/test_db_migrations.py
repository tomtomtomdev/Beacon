from pathlib import Path

import pytest

from beacon.adapters.persistence.db import connect, run_migrations


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "001_create_jobs.sql").write_text("CREATE TABLE jobs (id INTEGER PRIMARY KEY);")
    (directory / "002_create_companies.sql").write_text(
        "CREATE TABLE companies (id INTEGER PRIMARY KEY);"
    )
    return directory


def test_migrations_apply_in_numbered_order(tmp_path: Path, migrations_dir: Path) -> None:
    conn = connect(tmp_path / "beacon.db")

    applied = run_migrations(conn, migrations_dir)

    assert applied == ["001_create_jobs.sql", "002_create_companies.sql"]
    tables = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"jobs", "companies", "schema_migrations"} <= tables


def test_migrations_are_idempotent(tmp_path: Path, migrations_dir: Path) -> None:
    conn = connect(tmp_path / "beacon.db")
    run_migrations(conn, migrations_dir)

    assert run_migrations(conn, migrations_dir) == []
