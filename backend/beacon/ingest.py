"""CLI composition root: python -m beacon.ingest [--company SLUG].

Wiring only — connects settings, DB, seeds, adapters and the ingest use case.
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime

import httpx

from beacon.adapters.classify.factory import make_classifier
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.notify.factory import make_notifier
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.countries import SqliteCountryRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.llm_budget import SqliteLLMBudget
from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.adapters.persistence.settings import SqliteSettingsRepo
from beacon.adapters.seeds import parse_seed_csv
from beacon.adapters.sources.factory import make_companyless_sources, make_source_factory
from beacon.application.countries import seed_countries
from beacon.application.dedup import dedupe_jobs
from beacon.application.health_report import build_health_alerts
from beacon.application.ingest import ingest_all, ingest_companyless_source
from beacon.application.notify import match_saved_searches
from beacon.application.settings import effective_telegram_config
from beacon.config import Settings
from beacon.domain.company import SHADOW_ATS_TYPE


async def run_ingest(
    settings: Settings,
    *,
    only_company: str | None = None,
    only_source: str | None = None,
    poll_ats: bool = True,
    poll_boards: bool = True,
) -> int:
    """One poll cycle: ATS boards, then company-less boards, then dedup + notify. poll_ats /
    poll_boards let the scheduler run the two source families on their own intervals (SPEC §9);
    dedup + notify always run (idempotent), so either family's poll keeps the list consistent."""
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    seed_countries(SqliteCountryRepo(conn))

    company_repo = SqliteCompanyRepo(conn)
    for seed in parse_seed_csv(settings.seeds_path.read_text()):
        company_repo.upsert(seed)

    jobs = SqliteJobRepo(conn)
    now = datetime.now(UTC)
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    budget = SqliteLLMBudget(conn, cap=settings.llm_monthly_budget)

    # Heuristic-only until an Anthropic key is set, else a budget-gated tiered classifier
    # (LLM on the ambiguous residue). The LLM client is sync (the Classifier port is sync);
    # ingest is sequential, so a blocking classify stalls nothing that could run concurrently.
    with httpx.Client(timeout=30.0) as llm_client:
        classifier = make_classifier(
            llm_client, api_key=api_key, model=settings.llm_model, budget=budget
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            fetcher = PoliteClient(client)

            # ATS boards: one seed company each. Shadow rows (ats_type='none', left by a
            # prior company-less poll) are excluded — no adapter polls them.
            if only_source is None and poll_ats:
                ats = [c for c in company_repo.list_active() if c.ats_type != SHADOW_ATS_TYPE]
                if only_company is not None:
                    ats = [c for c in ats if c.ats_slug == only_company]
                    if not ats:
                        print(f"no active company with ats_slug={only_company!r}")
                        return 1
                results = await ingest_all(
                    ats, jobs, make_source_factory(fetcher), classifier, company_repo, now=now
                )
                for name, result in results.items():
                    print(
                        f"company={name} fetched={result.fetched}"
                        f" upserted={result.upserted} errors={result.errors}"
                    )

            # Company-less sources (HN, JobTech): one source, many employers per posting.
            if only_company is None and poll_boards:
                sources = make_companyless_sources(fetcher)
                if only_source is not None:
                    sources = [s for s in sources if s.source_id == only_source]
                    if not sources:
                        print(f"no company-less source with id={only_source!r}")
                        return 1
                for source in sources:
                    try:
                        result = await ingest_companyless_source(
                            source, jobs, company_repo, classifier, now=now
                        )
                    except Exception:
                        # A dead board never stops the run (rule 6); company-less sources have
                        # no per-company health, so we just log and move on.
                        logging.getLogger(__name__).exception(
                            "companyless_poll_failed source=%s", source.source_id
                        )
                        continue
                    print(
                        f"source={source.source_id} fetched={result.fetched}"
                        f" upserted={result.upserted} errors={result.errors}"
                    )

            # Cross-source dedup runs once after every board is upserted (SPEC §5 pipeline).
            dedup = dedupe_jobs(jobs)
            print(f"dedup groups={dedup.groups} duplicates={dedup.duplicates}")

            # Notify: match saved searches against the deduped canonical rows, alert once.
            # Creds set via the Settings UI (DB) win, falling back to BEACON_TELEGRAM_* env.
            telegram = effective_telegram_config(
                SqliteSettingsRepo(conn), settings.telegram_config()
            )
            # Source-health section: quarantined companies + stale registry snapshots ride the
            # same digest (SPEC §7) so silent decay surfaces even with no new matches.
            health_alerts, stale = build_health_alerts(
                company_repo, SqliteRegistriesMetaRepo(conn), now=now
            )
            match = await match_saved_searches(
                SqliteSearchRepo(conn),
                jobs,
                make_notifier(telegram, client),
                now=now,
                health_alerts=health_alerts,
                stale_registries=stale,
            )
            print(f"searches={match.searches_run} new_matches={match.new_matches}")

    if api_key:
        print(f"llm_calls_this_month={budget.calls_this_month()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll ATS boards and company-less sources.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--company", metavar="SLUG", help="only the ATS company with this ats_slug")
    target.add_argument("--source", metavar="ID", help="only this company-less source (hn/jobtech)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return asyncio.run(
        run_ingest(Settings.from_env(), only_company=args.company, only_source=args.source)
    )


if __name__ == "__main__":
    raise SystemExit(main())
