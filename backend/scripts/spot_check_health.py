"""Manual source-health spot-check — the slice-11 acceptance gate (live network).

Points a seed company at a nonsense Greenhouse slug (real 404 → `gone`), polls it three
times through the real PoliteClient + ingest pipeline, and proves:
  1. after 3 gone polls the company is quarantined (reason gone), polling stops;
  2. a job that existed on it never gets closed_at (failed polls never run the closed-sweep);
  3. the digest health section reports it;
then fixes the slug to a real board and proves the re-seed resets health and polling resumes.

    cd backend && uv run python scripts/spot_check_health.py

Live network only (never in the test suite). The mechanism is proven with fakes in
tests/unit/test_ingest.py, tests/integration/test_probe.py and tests/integration/test_health_report.py;
this exercises the real HTTP → SourceUnavailable → quarantine path end-to-end.
"""

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from beacon.adapters.classify.factory import make_classifier
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.llm_budget import SqliteLLMBudget
from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo
from beacon.adapters.sources.factory import SUPPORTED_ATS, make_source_factory
from beacon.application.company_health import get_company_health
from beacon.application.health_report import build_health_alerts
from beacon.application.ingest import ingest_all
from beacon.domain.company import Company
from beacon.domain.health import Health
from beacon.domain.job import NormalizedJob

NONSENSE_SLUG = "beacon-health-check-no-such-board-xyzzy"
REAL_SLUG = "tines"  # a verified Greenhouse board (slice 1)


def _seed_job(jobs: SqliteJobRepo, company_id: int, now: datetime) -> None:
    jobs.upsert(
        company_id,
        NormalizedJob(
            source_id="greenhouse",
            external_id="pre-existing-1",
            title="Engineer",
            url="https://example.test/1",
            description="Build things.",
            location_raw="Remote",
            country=None,
            city=None,
            posted_at=None,
            content_hash="pre-1",
        ),
        seen_at=now,
    )


def _closed_at(conn: sqlite3.Connection, external_id: str) -> str | None:
    row = conn.execute(
        "SELECT closed_at FROM jobs WHERE external_id = ?", (external_id,)
    ).fetchone()
    return None if row is None or row["closed_at"] is None else str(row["closed_at"])


async def _run() -> int:
    now = datetime.now(UTC)
    with TemporaryDirectory() as tmp:
        conn = connect(Path(tmp) / "beacon.db")
        run_migrations(conn, MIGRATIONS_DIR)
        companies = SqliteCompanyRepo(conn)
        jobs = SqliteJobRepo(conn)
        meta = SqliteRegistriesMetaRepo(conn)

        company = companies.upsert(Company("HealthCheckCo", "greenhouse", NONSENSE_SLUG, "IE", 1))
        assert company.id is not None  # noqa: S101 — freshly inserted
        _seed_job(jobs, company.id, now)

        budget = SqliteLLMBudget(conn, cap=0)
        with httpx.Client(timeout=15.0) as llm_client:
            classifier = make_classifier(llm_client, api_key=None, model="x", budget=budget)
            async with httpx.AsyncClient(timeout=15.0) as client:
                source_for = make_source_factory(PoliteClient(client, min_interval=0.0))

                print(f"=== 3 polls of nonsense slug {NONSENSE_SLUG!r} (expect 404 → gone) ===")
                for cycle in range(1, 4):
                    await ingest_all(
                        companies.list_active(), jobs, source_for, classifier, companies, now=now
                    )
                    health = companies.get_health(company.id)
                    print(
                        f"poll {cycle}: health={health.health.value}"
                        f" failures={health.consecutive_failures} reason={health.reason}"
                    )

                quarantined = companies.get_health(company.id)
                jobs_frozen = _closed_at(conn, "pre-existing-1") is None
                alerts, _stale = build_health_alerts(companies, meta, now=now)
                print(f"\nquarantined: {quarantined.health is Health.QUARANTINED}")
                print(
                    f"reason gone: {quarantined.reason is not None and quarantined.reason.value == 'gone'}"
                )
                print(f"pre-existing job still open (never closed): {jobs_frozen}")
                print(f"digest health alerts: {[(a.company, a.reason) for a in alerts]}")

                print(f"\n=== fix the slug → {REAL_SLUG!r}, re-seed resets health, poll again ===")
                companies.upsert(Company("HealthCheckCo", "greenhouse", REAL_SLUG, "IE", 1))
                after_reset = companies.get_health(company.id)
                print(f"after re-seed: health={after_reset.health.value} (expect ok)")

                results = await ingest_all(
                    companies.list_active(), jobs, source_for, classifier, companies, now=now
                )
                recovered = companies.get_health(company.id)
                result = results.get("HealthCheckCo")
                print(
                    f"recovery poll: health={recovered.health.value}"
                    f" upserted={result.upserted if result else 0}"
                )

                view = get_company_health(companies, SUPPORTED_ATS)
                print(
                    f"\n/companies/health summary: healthy={view.summary.healthy}"
                    f" quarantined={view.summary.quarantined} seed={view.summary.seed}"
                )

        ok = (
            quarantined.health is Health.QUARANTINED
            and quarantined.reason is not None
            and quarantined.reason.value == "gone"
            and jobs_frozen
            and bool(alerts)
            and after_reset.health is Health.OK
            and recovered.health is Health.OK
            and result is not None
            and result.upserted > 0
        )
        print("\nACCEPTANCE", "OK" if ok else "FAILED")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
