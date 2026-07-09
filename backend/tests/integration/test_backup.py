"""Nightly SQLite backup: a consistent online copy, timestamped, pruned to the newest N."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from beacon.adapters.persistence.backup import backup_database


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('hello')")
    conn.commit()
    conn.close()


def test_backup_copies_the_database_contents(tmp_path: Path) -> None:
    db_path = tmp_path / "beacon.db"
    make_db(db_path)

    dest = backup_database(db_path, tmp_path / "backups", datetime(2026, 7, 9, 4, 0, tzinfo=UTC))

    assert dest.exists()
    restored = sqlite3.connect(dest)
    assert restored.execute("SELECT v FROM t").fetchone()[0] == "hello"
    restored.close()


def test_backup_filename_is_timestamped(tmp_path: Path) -> None:
    db_path = tmp_path / "beacon.db"
    make_db(db_path)

    dest = backup_database(db_path, tmp_path / "backups", datetime(2026, 7, 9, 4, 30, tzinfo=UTC))

    assert dest.name == "beacon-20260709-043000.db"


def test_backup_prunes_to_the_newest_kept(tmp_path: Path) -> None:
    db_path = tmp_path / "beacon.db"
    make_db(db_path)
    backups = tmp_path / "backups"

    for day in range(1, 6):  # five nightly backups
        backup_database(db_path, backups, datetime(2026, 7, day, 4, 0, tzinfo=UTC), keep=3)

    remaining = sorted(p.name for p in backups.glob("beacon-*.db"))
    assert remaining == [
        "beacon-20260703-040000.db",
        "beacon-20260704-040000.db",
        "beacon-20260705-040000.db",
    ]
