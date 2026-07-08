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
from beacon.adapters.notify.stdout import StdoutNotifier
from beacon.adapters.notify.telegram import TelegramNotifier
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.adapters.seeds import parse_seed_csv
from beacon.adapters.sources.factory import make_companyless_sources, make_source_factory
from beacon.application.dedup import dedupe_jobs
from beacon.application.ingest import SHADOW_ATS_TYPE, ingest_all, ingest_companyless_source
from beacon.application.notify import match_saved_searches
from beacon.application.ports import Notifier
from beacon.config import Settings


def _make_notifier(settings: Settings, client: httpx.AsyncClient) -> Notifier:
    """TelegramNotifier when a bot token + chat_id are configured, else StdoutNotifier —
    so ingest never fails just because Telegram isn't set up yet."""
    token = settings.telegram_bot_token
    if token is not None and settings.telegram_chat_id is not None:
        return TelegramNotifier(
            client, bot_token=token.get_secret_value(), chat_id=settings.telegram_chat_id
        )
    return StdoutNotifier()


async def _run(settings: Settings, *, only_company: str | None, only_source: str | None) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)

    company_repo = SqliteCompanyRepo(conn)
    for seed in parse_seed_csv(settings.seeds_path.read_text()):
        company_repo.upsert(seed)

    jobs = SqliteJobRepo(conn)
    classifier = HeuristicClassifier()
    now = datetime.now(UTC)

    async with httpx.AsyncClient(timeout=15.0) as client:
        fetcher = PoliteClient(client)

        # ATS boards: one seed company each. Shadow rows (ats_type='none', left by a prior
        # company-less poll) are excluded — no adapter polls them.
        if only_source is None:
            ats = [c for c in company_repo.list_active() if c.ats_type != SHADOW_ATS_TYPE]
            if only_company is not None:
                ats = [c for c in ats if c.ats_slug == only_company]
                if not ats:
                    print(f"no active company with ats_slug={only_company!r}")
                    return 1
            results = await ingest_all(ats, jobs, make_source_factory(fetcher), classifier, now=now)
            for name, result in results.items():
                print(
                    f"company={name} fetched={result.fetched}"
                    f" upserted={result.upserted} errors={result.errors}"
                )

        # Company-less sources (HN, JobTech): one source, many employers parsed per posting.
        if only_company is None:
            sources = make_companyless_sources(fetcher)
            if only_source is not None:
                sources = [s for s in sources if s.source_id == only_source]
                if not sources:
                    print(f"no company-less source with id={only_source!r}")
                    return 1
            for source in sources:
                result = await ingest_companyless_source(
                    source, jobs, company_repo, classifier, now=now
                )
                print(
                    f"source={source.source_id} fetched={result.fetched}"
                    f" upserted={result.upserted} errors={result.errors}"
                )

        # Cross-source dedup runs once after every board is upserted (SPEC §5 pipeline).
        dedup = dedupe_jobs(jobs)
        print(f"dedup groups={dedup.groups} duplicates={dedup.duplicates}")

        # Notify: match saved searches against the deduped canonical rows, alert once.
        match = await match_saved_searches(
            SqliteSearchRepo(conn), jobs, _make_notifier(settings, client), now=now
        )
        print(f"searches={match.searches_run} new_matches={match.new_matches}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll ATS boards and company-less sources.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--company", metavar="SLUG", help="only the ATS company with this ats_slug")
    target.add_argument("--source", metavar="ID", help="only this company-less source (hn/jobtech)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return asyncio.run(
        _run(Settings.from_env(), only_company=args.company, only_source=args.source)
    )


if __name__ == "__main__":
    raise SystemExit(main())
