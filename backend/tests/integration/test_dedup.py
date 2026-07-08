import sqlite3
from datetime import UTC, datetime

import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.dedup import dedupe_jobs
from beacon.application.ports import JobFilters
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

POLL_AT = datetime(2026, 7, 8, 6, 0, tzinfo=UTC)

# A realistic-length JD: the same posting reformatted on a second board stays a few bits
# away, while a genuinely different role is 15+ bits off (see test_dedup.py for the boundary).
BASE = (
    "We are hiring a Senior Backend Engineer to design, build and operate scalable "
    "distributed systems that power our platform. You will own services end to end, from "
    "API design through deployment and on-call, working primarily in Python and Go. You "
    "will collaborate with product and design, mentor other engineers, improve our CI and "
    "observability, and help shape the technical architecture as we scale across Europe."
)


def _job(source: str, external_id: str, title: str, description: str) -> NormalizedJob:
    return NormalizedJob(
        source_id=source,
        external_id=external_id,
        title=title,
        url=f"https://{source}.test/{external_id}",
        description=description,
        location_raw="Dublin, Ireland",
        country="IE",
        city="Dublin",
        posted_at=datetime(2026, 7, 1, tzinfo=UTC),
        content_hash=f"hash-{source}-{external_id}",
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


def test_dedupe_links_same_role_from_two_sources(repo: SqliteJobRepo, company_id: int) -> None:
    repo.upsert(company_id, _job("greenhouse", "gh1", "Backend Engineer", BASE), seen_at=POLL_AT)
    repo.upsert(
        company_id,
        _job("lever", "lv1", "Backend Engineer", BASE + " Apply on our careers page."),
        seen_at=POLL_AT,
    )

    result = dedupe_jobs(repo)

    assert (result.groups, result.duplicates) == (1, 1)
    # The earliest-inserted row (lowest id) is canonical; the other points at it.
    rows = repo._conn.execute("SELECT id, source_id, canonical_id FROM jobs ORDER BY id").fetchall()
    canonical, duplicate = rows
    assert canonical["canonical_id"] is None
    assert duplicate["canonical_id"] == canonical["id"]


def test_jobs_search_returns_canonical_only(repo: SqliteJobRepo, company_id: int) -> None:
    repo.upsert(company_id, _job("greenhouse", "gh1", "Backend Engineer", BASE), seen_at=POLL_AT)
    repo.upsert(company_id, _job("lever", "lv1", "Backend Engineer", BASE), seen_at=POLL_AT)
    repo.upsert(company_id, _job("greenhouse", "gh2", "Frontend Engineer", BASE), seen_at=POLL_AT)

    dedupe_jobs(repo)

    page = repo.search(JobFilters())
    # Two dupes collapse to one; the distinct frontend role stays — two rows, not three.
    assert page.total == 2
    assert sorted(job.title for job in page.jobs) == ["Backend Engineer", "Frontend Engineer"]


def test_job_detail_lists_every_underlying_source(repo: SqliteJobRepo, company_id: int) -> None:
    repo.upsert(company_id, _job("greenhouse", "gh1", "Backend Engineer", BASE), seen_at=POLL_AT)
    repo.upsert(company_id, _job("lever", "lv1", "Backend Engineer", BASE), seen_at=POLL_AT)
    dedupe_jobs(repo)
    (canonical_id,) = repo._conn.execute(
        "SELECT id FROM jobs WHERE canonical_id IS NULL"
    ).fetchone()

    # Asking for either the canonical id or the duplicate id resolves to the same detail.
    duplicate_id = repo._conn.execute(
        "SELECT id FROM jobs WHERE canonical_id IS NOT NULL"
    ).fetchone()["id"]
    detail = repo.get_job_detail(duplicate_id)

    assert detail is not None
    assert detail.id == canonical_id
    assert detail.description == BASE
    assert {source.source for source in detail.duplicate_sources} == {"greenhouse", "lever"}


def test_get_job_detail_returns_none_for_missing_id(repo: SqliteJobRepo, company_id: int) -> None:
    assert repo.get_job_detail(9999) is None


def test_dedupe_is_idempotent(repo: SqliteJobRepo, company_id: int) -> None:
    repo.upsert(company_id, _job("greenhouse", "gh1", "Backend Engineer", BASE), seen_at=POLL_AT)
    repo.upsert(company_id, _job("lever", "lv1", "Backend Engineer", BASE), seen_at=POLL_AT)

    first = dedupe_jobs(repo)
    second = dedupe_jobs(repo)

    assert (first.groups, first.duplicates) == (second.groups, second.duplicates) == (1, 1)


def test_no_false_merge_persists_distinct_roles(repo: SqliteJobRepo, company_id: int) -> None:
    repo.upsert(company_id, _job("greenhouse", "gh1", "Senior iOS Engineer", BASE), seen_at=POLL_AT)
    repo.upsert(company_id, _job("lever", "lv1", "Senior Android Engineer", BASE), seen_at=POLL_AT)

    result = dedupe_jobs(repo)

    assert (result.groups, result.duplicates) == (0, 0)
    assert repo.search(JobFilters()).total == 2
