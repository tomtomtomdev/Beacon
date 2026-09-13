"""CLI composition root: python -m beacon.retier.

Wiring only. A one-shot over rows that were ingested before the home market was a tier
(SPEC §3/§6, slice 15): every stored posting located in the home country is moved onto the
tier resolve_tier now gives it, and the evidence sentence that decided its old tier is
cleared with it.

Needs no classifier, no network and no key — it reads the country column and writes the
tier column, so it can neither change a content_hash nor spend an LLM call. Idempotent: a
second run retiers nothing.
"""

import argparse

from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.backfill import backfill_home_market
from beacon.config import Settings
from beacon.logging_setup import configure_cli_logging


def _run(settings: Settings) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)

    retiered = backfill_home_market(SqliteJobRepo(conn))

    print(f"retier retiered={retiered}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Retier stored home-market postings (one-shot; idempotent)."
    )
    parser.parse_args(argv)

    configure_cli_logging()
    return _run(Settings.from_env())


if __name__ == "__main__":
    raise SystemExit(main())
