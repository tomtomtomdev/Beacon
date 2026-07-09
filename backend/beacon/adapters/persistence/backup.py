"""Nightly SQLite backup (SPEC §9). Uses sqlite3's online backup API for a consistent copy
even while the DB is in use, writes a timestamped file, and prunes to the newest `keep`."""

import sqlite3
from datetime import datetime
from pathlib import Path

_KEEP_DEFAULT = 14  # two weeks of nightly backups


def backup_database(
    db_path: Path, backups_dir: Path, now: datetime, *, keep: int = _KEEP_DEFAULT
) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    dest = backups_dir / f"beacon-{now.strftime('%Y%m%d-%H%M%S')}.db"

    source = sqlite3.connect(db_path)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    _prune(backups_dir, keep)
    return dest


def _prune(backups_dir: Path, keep: int) -> None:
    # Timestamped names sort chronologically, so the tail is the oldest.
    backups = sorted(backups_dir.glob("beacon-*.db"))
    for stale in backups[:-keep] if keep > 0 else backups:
        stale.unlink()
