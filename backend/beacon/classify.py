"""CLI composition root: python -m beacon.classify — backfill classification.

Wiring only. Classifies every job in the DB that was never classified (categories IS
NULL), e.g. rows ingested before the classifier existed. Cached by design: already-
classified rows (including honest empty results) are left untouched.
"""

import argparse
import logging

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.backfill import backfill_classifications
from beacon.config import Settings


def _run(settings: Settings) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    count = backfill_classifications(SqliteJobRepo(conn), HeuristicClassifier())
    print(f"backfill classified={count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill category/level on unclassified jobs.")
    parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return _run(Settings.from_env())


if __name__ == "__main__":
    raise SystemExit(main())
