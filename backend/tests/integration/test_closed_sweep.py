"""Closed-posting sweep: a job absent from N consecutive *successful* polls of its source
gets closed_at; failed polls never run the sweep, so they never close anything (SPEC §7)."""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

POLL_AT = datetime(2026, 7, 4, 6, 0, tzinfo=UTC)


def make_job(external_id: str, source_id: str = "greenhouse") -> NormalizedJob:
    return NormalizedJob(
        source_id=source_id,
        external_id=external_id,
        title=f"Engineer {external_id}",
        url=f"https://example.test/{external_id}",
        description="Build things.",
        location_raw="Remote",
        country=None,
        city=None,
        posted_at=None,
        content_hash=f"hash-{external_id}",
    )


def seed_company(db: sqlite3.Connection, name: str = "Tines") -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(
            name=name, ats_type="greenhouse", ats_slug=name.lower(), country_hq="IE", priority=2
        )
    )
    assert company.id is not None
    return company.id


def closed_at(db: sqlite3.Connection, external_id: str) -> str | None:
    row = db.execute("SELECT closed_at FROM jobs WHERE external_id = ?", (external_id,)).fetchone()
    value = row["closed_at"]
    return None if value is None else str(value)


def misses(db: sqlite3.Connection, external_id: str) -> int:
    row = db.execute(
        "SELECT consecutive_misses FROM jobs WHERE external_id = ?", (external_id,)
    ).fetchone()
    return int(row["consecutive_misses"])


def test_present_job_stays_open_with_zero_misses(db: sqlite3.Connection) -> None:
    company_id = seed_company(db)
    jobs = SqliteJobRepo(db)
    jobs.upsert(company_id, make_job("1"), seen_at=POLL_AT)

    jobs.sweep_absent_jobs("greenhouse", company_id, {"1"}, POLL_AT, threshold=2)

    assert misses(db, "1") == 0
    assert closed_at(db, "1") is None


def test_absent_job_closes_after_threshold_consecutive_misses(db: sqlite3.Connection) -> None:
    company_id = seed_company(db)
    jobs = SqliteJobRepo(db)
    jobs.upsert(company_id, make_job("1"), seen_at=POLL_AT)
    jobs.upsert(company_id, make_job("2"), seen_at=POLL_AT)

    # Poll 1: only job 1 present → job 2 missed once (threshold 2, not yet closed).
    jobs.sweep_absent_jobs("greenhouse", company_id, {"1"}, POLL_AT, threshold=2)
    assert misses(db, "2") == 1
    assert closed_at(db, "2") is None

    # Poll 2: job 2 still absent → reaches threshold → closed.
    later = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
    newly_closed = jobs.sweep_absent_jobs("greenhouse", company_id, {"1"}, later, threshold=2)
    assert misses(db, "2") == 2
    assert closed_at(db, "2") == later.isoformat()
    assert newly_closed == 1
    assert closed_at(db, "1") is None  # present every poll


def test_reappearing_job_resets_misses_and_reopens(db: sqlite3.Connection) -> None:
    company_id = seed_company(db)
    jobs = SqliteJobRepo(db)
    jobs.upsert(company_id, make_job("2"), seen_at=POLL_AT)
    jobs.sweep_absent_jobs("greenhouse", company_id, set(), POLL_AT, threshold=2)
    jobs.sweep_absent_jobs("greenhouse", company_id, set(), POLL_AT, threshold=2)
    assert closed_at(db, "2") is not None  # closed after two empty successful polls

    jobs.sweep_absent_jobs("greenhouse", company_id, {"2"}, POLL_AT, threshold=2)

    assert misses(db, "2") == 0
    assert closed_at(db, "2") is None  # present again → reopened


def test_sweep_is_scoped_to_one_company_on_a_shared_ats_source(db: sqlite3.Connection) -> None:
    # Two greenhouse companies share source_id 'greenhouse'; one company's poll must not
    # touch the other's jobs.
    tines = seed_company(db, "Tines")
    other = seed_company(db, "Other")
    jobs = SqliteJobRepo(db)
    jobs.upsert(tines, make_job("t1"), seen_at=POLL_AT)
    jobs.upsert(other, make_job("o1"), seen_at=POLL_AT)

    # Tines poll returns nothing → t1 missed, but o1 (Other's job) is untouched.
    jobs.sweep_absent_jobs("greenhouse", tines, set(), POLL_AT, threshold=2)

    assert misses(db, "t1") == 1
    assert misses(db, "o1") == 0
