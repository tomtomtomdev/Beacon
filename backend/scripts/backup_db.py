"""Nightly SQLite backup (SPEC §9). Run manually or from cron/launchd:

    uv run python scripts/backup_db.py

Writes a timestamped consistent copy under Settings.backups_dir and prunes to the newest N.
The scheduler runs this automatically (nightly job); this script is the manual/cron entry.
"""

from datetime import UTC, datetime

from beacon.adapters.persistence.backup import backup_database
from beacon.config import Settings


def main() -> int:
    settings = Settings.from_env()
    dest = backup_database(settings.db_path, settings.backups_dir, datetime.now(UTC))
    print(f"backup written to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
