"""The open-job histogram by country (slice 20a).

The rollup behind the "other markets" affordance: which countries actually hold open,
canonical jobs, and how many. The repo counts; what a country *means* — target market or
not — is the domain's question, answered in `partition_markets`.
"""

import sqlite3
from datetime import UTC, datetime

import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

POLL_AT = datetime(2026, 9, 15, 5, 0, tzinfo=UTC)


def _job(external_id: str, country: str | None) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title="Senior Backend Engineer",
        url=f"https://greenhouse.test/{external_id}",
        description="Build and operate distributed systems.",
        location_raw=country or "Anywhere in the World",
        country=country,
        city=None,
        posted_at=datetime(2026, 9, 1, tzinfo=UTC),
        content_hash=f"hash-{external_id}",
    )


@pytest.fixture
def repo(db: sqlite3.Connection) -> SqliteJobRepo:
    return SqliteJobRepo(db)


@pytest.fixture
def company_id(db: sqlite3.Connection) -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(
            name="Immutable",
            ats_type="greenhouse",
            ats_slug="immutable",
            country_hq="IE",
            priority=1,
        )
    )
    assert company.id is not None
    return company.id


def test_counts_open_canonical_jobs_by_country(repo: SqliteJobRepo, company_id: int) -> None:
    for external_id, country in (("a", "DE"), ("b", "DE"), ("c", "IN")):
        repo.upsert(company_id, _job(external_id, country), POLL_AT)

    assert repo.count_open_by_country() == {"DE": 2, "IN": 1}


def test_a_duplicate_does_not_count_twice(
    repo: SqliteJobRepo, company_id: int, db: sqlite3.Connection
) -> None:
    """The same role on two boards is one job. Counting both is how 1,843 becomes 1,940."""
    for external_id in ("canonical", "duplicate"):
        repo.upsert(company_id, _job(external_id, "DE"), POLL_AT)
    ids = {
        row["external_id"]: row["id"]
        for row in db.execute("SELECT id, external_id FROM jobs").fetchall()
    }
    repo.set_canonical_links({ids["duplicate"]: ids["canonical"], ids["canonical"]: None})

    assert repo.count_open_by_country() == {"DE": 1}


def test_a_closed_job_is_not_counted(repo: SqliteJobRepo, company_id: int) -> None:
    """A chip promising 216 German jobs that opens onto 40 live ones is the slice's own defect."""
    repo.upsert(company_id, _job("open", "DE"), POLL_AT)
    repo.upsert(company_id, _job("gone", "DE"), POLL_AT)
    repo.sweep_absent_jobs("greenhouse", company_id, {"open"}, POLL_AT, threshold=1)

    assert repo.count_open_by_country() == {"DE": 1}


def test_a_job_with_no_country_is_absent_from_the_histogram(
    repo: SqliteJobRepo, company_id: int
) -> None:
    """Unparsed locations are candidate C's 898 jobs, not a market. The port must not invent
    an "unknown" key the domain would then have to special-case away."""
    repo.upsert(company_id, _job("placed", "DE"), POLL_AT)
    repo.upsert(company_id, _job("unplaced", None), POLL_AT)

    assert repo.count_open_by_country() == {"DE": 1}
