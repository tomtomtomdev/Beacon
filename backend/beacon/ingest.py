"""CLI composition root: python -m beacon.ingest [--company SLUG].

Wiring only — connects settings, DB, seeds, adapters and the ingest use case.
"""

import argparse
import asyncio
import time
from datetime import UTC, datetime

import httpx

from beacon.adapters.classify.factory import make_classifier
from beacon.adapters.http.credentials import ApiKeyHeader, Bearer, HostCredential
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.countries import SqliteCountryRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.llm_budget import SqliteLLMBudget
from beacon.adapters.seeds import parse_seed_csv
from beacon.adapters.sources.factory import make_companyless_sources, make_source_factory
from beacon.adapters.sources.bundesagentur import BUNDESAGENTUR_HOST, BUNDESAGENTUR_API_KEY
from beacon.adapters.sources.nav import NAV_HOST
from beacon.application.countries import seed_countries
from beacon.application.dedup import dedupe_jobs
from beacon.application.ingest import ingest_all, ingest_companyless_all
from beacon.application.ports import JobSource
from beacon.application.probe import probe_quarantined
from beacon.config import Settings
from beacon.domain.company import SHADOW_ATS_TYPE, Company
from beacon.notify import send_digest
from beacon.logging_setup import configure_cli_logging


def host_credentials(settings: Settings) -> dict[str, HostCredential]:
    """Per-host credentials for the HTTP door. Only the hosts we actually have a token for,
    so a missing credential means a source is not wired rather than a 401 every poll.
    Bundesagentur's key is a published public constant, so it is always present."""
    credentials: dict[str, HostCredential] = {
        BUNDESAGENTUR_HOST: ApiKeyHeader("X-API-Key", BUNDESAGENTUR_API_KEY),
    }
    if settings.nav_api_token:
        credentials[NAV_HOST] = Bearer(settings.nav_api_token)
    return credentials


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
    # (LLM on the ambiguous residue). The LLM client is sync (the Classifier port is sync), so
    # since slice 29b a classify that calls the LLM briefly stalls the other sources' fetches —
    # accepted: it is one call per unseen content_hash, under a monthly cap.
    with httpx.Client(timeout=30.0) as llm_client:
        classifier = make_classifier(
            llm_client, api_key=api_key, model=settings.llm_model, budget=budget
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            fetcher = PoliteClient(client, credentials=host_credentials(settings))

            # ATS boards: one seed company each. Shadow rows (ats_type='none', left by a
            # prior company-less poll) are excluded — no adapter polls them.
            ats: list[Company] = []
            if only_source is None and poll_ats:
                ats = [c for c in company_repo.list_active() if c.ats_type != SHADOW_ATS_TYPE]
                if only_company is not None:
                    ats = [c for c in ats if c.ats_slug == only_company]
                    if not ats:
                        print(f"no active company with ats_slug={only_company!r}")
                        return 1

            # Company-less sources (HN, JobTech, Himalayas, MyCareersFuture, …): one source,
            # many employers per posting.
            boards: list[JobSource] = []
            if only_company is None and poll_boards:
                boards = make_companyless_sources(
                    fetcher, nav_authenticated=settings.nav_api_token is not None
                )
                if only_source is not None:
                    boards = [s for s in boards if s.source_id == only_source]
                    if not boards:
                        print(f"no company-less source with id={only_source!r}")
                        return 1

            async def poll_ats_phase() -> None:
                started = time.monotonic()
                results = await ingest_all(
                    ats, jobs, make_source_factory(fetcher), classifier, company_repo, now=now
                )
                for name, result in results.items():
                    print(
                        f"company={name} fetched={result.fetched}"
                        f" upserted={result.upserted} errors={result.errors} secs={result.secs}"
                    )
                print(f"phase=ats secs={time.monotonic() - started:.1f}")

            async def poll_boards_phase() -> None:
                started = time.monotonic()
                results = await ingest_companyless_all(
                    boards, jobs, company_repo, classifier, now=now
                )
                for source_id, result in results.items():
                    print(
                        f"source={source_id} fetched={result.fetched}"
                        f" upserted={result.upserted} errors={result.errors} secs={result.secs}"
                    )
                print(f"phase=boards secs={time.monotonic() - started:.1f}")

            # Both families overlap (slice 29b); each phase is a no-op when its list is empty.
            started = time.monotonic()
            await asyncio.gather(poll_ats_phase(), poll_boards_phase())
            print(f"phase=poll secs={time.monotonic() - started:.1f}")

            # Cross-source dedup runs once after every board is upserted (SPEC §5 pipeline).
            dedup = dedupe_jobs(jobs)
            print(f"dedup groups={dedup.groups} duplicates={dedup.duplicates}")

            # Notify: match saved searches against the deduped canonical rows, alert once.
            # Same tail as the standalone dispatches (beacon.notify), so the poll's digest and
            # run.sh's launch/close digests resolve creds and assemble the digest identically.
            match = await send_digest(conn, settings, client, now=now)
            print(f"searches={match.searches_run} new_matches={match.new_matches}")

    if api_key:
        print(f"llm_calls_this_month={budget.calls_this_month()}")
    return 0


async def run_probe(settings: Settings) -> int:
    """The weekly restore probe (SPEC §7): retry each quarantined source once and restore the
    ones that recovered. Its own composition root so the scheduler can run it on its own cron."""
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    company_repo = SqliteCompanyRepo(conn)
    for seed in parse_seed_csv(settings.seeds_path.read_text()):
        company_repo.upsert(seed)

    jobs = SqliteJobRepo(conn)
    now = datetime.now(UTC)
    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    budget = SqliteLLMBudget(conn, cap=settings.llm_monthly_budget)

    with httpx.Client(timeout=30.0) as llm_client:
        classifier = make_classifier(
            llm_client, api_key=api_key, model=settings.llm_model, budget=budget
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            result = await probe_quarantined(
                company_repo,
                jobs,
                make_source_factory(PoliteClient(client, credentials=host_credentials(settings))),
                classifier,
                now=now,
            )
    print(f"probe probed={result.probed} restored={result.restored}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Poll ATS boards and company-less sources.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--company", metavar="SLUG", help="only the ATS company with this ats_slug")
    target.add_argument(
        "--source",
        metavar="ID",
        help=(
            "only this company-less source (hn/jobtech/remoteok/weworkremotely/himalayas/"
            "mycareersfuture/arbeitnow/bundesagentur/nav)"
        ),
    )
    args = parser.parse_args(argv)

    configure_cli_logging()
    return asyncio.run(
        run_ingest(Settings.from_env(), only_company=args.company, only_source=args.source)
    )


if __name__ == "__main__":
    raise SystemExit(main())
