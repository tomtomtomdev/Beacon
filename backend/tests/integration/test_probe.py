"""Weekly probe (SPEC §7): retry each quarantined source once. Success auto-restores it to
ok, resets counters, and resumes polling (jobs upserted); a still-failing probe leaves the
source quarantined with its counters untouched (no inflation)."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.errors import SourceUnavailable
from beacon.application.probe import ProbeResult, probe_quarantined
from beacon.application.ports import RawPosting
from beacon.domain.classification import Classification, Level
from beacon.domain.company import Company
from beacon.domain.health import FailureKind, Health, SourceHealth
from beacon.domain.job import NormalizedJob

NOW = datetime(2026, 7, 9, 6, 0, tzinfo=UTC)


class OkSource:
    """A recovered board: fetch returns one posting."""

    source_id = "greenhouse"

    async def fetch(self) -> list[RawPosting]:
        return [{"id": "1"}]

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        return NormalizedJob(
            source_id="greenhouse",
            external_id=str(raw["id"]),
            title="Engineer",
            url="https://example.test/1",
            description="Build things.",
            location_raw="",
            country=None,
            city=None,
            posted_at=None,
            content_hash="h1",
        )


class DownSource:
    """A board still failing at the HTTP level."""

    source_id = "greenhouse"

    def __init__(self, kind: FailureKind) -> None:
        self._kind = kind

    async def fetch(self) -> list[RawPosting]:
        raise SourceUnavailable(self._kind)

    def normalize(self, raw: RawPosting) -> NormalizedJob:  # pragma: no cover - never reached
        raise AssertionError("down source never normalizes")


class StubClassifier:
    def classify(self, job: NormalizedJob) -> Classification:
        return Classification(categories=frozenset(), level=Level.UNSPECIFIED)


def seed(db: sqlite3.Connection, name: str = "Tines") -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(
            name=name, ats_type="greenhouse", ats_slug=name.lower(), country_hq="IE", priority=2
        )
    )
    assert company.id is not None
    return company.id


def quarantine(repo: SqliteCompanyRepo, company_id: int) -> None:
    repo.set_health(
        company_id,
        SourceHealth(consecutive_failures=3, health=Health.QUARANTINED, reason=FailureKind.GONE),
    )


def job_count(db: sqlite3.Connection, company_id: int) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS n FROM jobs WHERE company_id = ?", (company_id,)
    ).fetchone()
    return int(row["n"])


async def test_probe_restores_a_recovered_source_and_resumes_polling(
    db: sqlite3.Connection,
) -> None:
    repo = SqliteCompanyRepo(db)
    jobs = SqliteJobRepo(db)
    company_id = seed(db)
    quarantine(repo, company_id)

    result = await probe_quarantined(repo, jobs, lambda _c: OkSource(), StubClassifier(), now=NOW)

    assert result == ProbeResult(probed=1, restored=1)
    restored = repo.get_health(company_id)
    assert restored.health is Health.OK
    assert restored.consecutive_failures == 0
    assert restored.last_success_at == NOW
    assert job_count(db, company_id) == 1  # polling resumed — the posting was upserted


async def test_probe_leaves_a_still_down_source_quarantined_without_inflation(
    db: sqlite3.Connection,
) -> None:
    repo = SqliteCompanyRepo(db)
    jobs = SqliteJobRepo(db)
    company_id = seed(db)
    quarantine(repo, company_id)

    result = await probe_quarantined(
        repo, jobs, lambda _c: DownSource(FailureKind.GONE), StubClassifier(), now=NOW
    )

    assert result == ProbeResult(probed=1, restored=0)
    still_down = repo.get_health(company_id)
    assert still_down.health is Health.QUARANTINED
    assert still_down.consecutive_failures == 3  # NOT 4 — a failed probe never inflates counters


async def test_probe_ignores_healthy_companies(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    jobs = SqliteJobRepo(db)
    seed(db)  # healthy, never quarantined

    result = await probe_quarantined(repo, jobs, lambda _c: OkSource(), StubClassifier(), now=NOW)

    assert result == ProbeResult(probed=0, restored=0)
