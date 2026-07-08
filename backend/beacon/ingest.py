"""CLI composition root: python -m beacon.ingest [--company SLUG].

Wiring only — connects settings, DB, seeds, adapters and the ingest use case.
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime

import httpx

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.seeds import parse_seed_csv
from beacon.adapters.sources.factory import make_source_factory
from beacon.application.dedup import dedupe_jobs
from beacon.application.ingest import ingest_all
from beacon.config import Settings


async def _run(settings: Settings, only_slug: str | None) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)

    company_repo = SqliteCompanyRepo(conn)
    for seed in parse_seed_csv(settings.seeds_path.read_text()):
        company_repo.upsert(seed)

    companies = company_repo.list_active()
    if only_slug is not None:
        companies = [c for c in companies if c.ats_slug == only_slug]
        if not companies:
            print(f"no active company with ats_slug={only_slug!r}")
            return 1

    jobs = SqliteJobRepo(conn)
    async with httpx.AsyncClient(timeout=15.0) as client:
        results = await ingest_all(
            companies,
            jobs,
            make_source_factory(PoliteClient(client)),
            HeuristicClassifier(),
            now=datetime.now(UTC),
        )

    for name, result in results.items():
        print(
            f"company={name} fetched={result.fetched}"
            f" upserted={result.upserted} errors={result.errors}"
        )

    # Cross-source dedup runs once after every board is upserted (SPEC §5 pipeline).
    dedup = dedupe_jobs(jobs)
    print(f"dedup groups={dedup.groups} duplicates={dedup.duplicates}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll ATS boards and upsert jobs.")
    parser.add_argument("--company", metavar="SLUG", help="only the company with this ats_slug")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return asyncio.run(_run(Settings.from_env(), args.company))


if __name__ == "__main__":
    raise SystemExit(main())
