"""CLI composition root: python -m beacon.relocate.

Wiring only. A one-shot over rows whose location string was parsed by an earlier, poorer
parser (SPEC §4/§5.1, slice 17): every stored posting with no country is re-read, and the
country the string names is written where the parser now finds one.

Needs no classifier, no network and no key — location.py keeps the raw string on the row
for exactly this ("a better parser can re-parse without re-fetching"), so it can neither
change a content_hash nor spend an LLM call. Idempotent: a second run fills nothing.

Fills only where country IS NULL, never overwriting one an adapter established, and
reports the residue it deliberately left alone. Read `scripts/spot_check_locations.py`
before keeping a run, and back the DB up first (`scripts/backup_db.py`).
"""

import argparse

from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.backfill import backfill_locations
from beacon.config import Settings
from beacon.logging_setup import configure_cli_logging


def _run(settings: Settings) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)

    result = backfill_locations(SqliteJobRepo(conn))

    print(f"relocate filled={result.filled} residue={result.residue} retiered={result.retiered}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-parse stored location strings that resolved no country (one-shot; idempotent)."
    )
    parser.parse_args(argv)

    configure_cli_logging()
    return _run(Settings.from_env())


if __name__ == "__main__":
    raise SystemExit(main())
