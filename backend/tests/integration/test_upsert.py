import sqlite3
from datetime import UTC, datetime

import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

FIRST_POLL = datetime(2026, 7, 4, 6, 0, tzinfo=UTC)
SECOND_POLL = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def make_job(title: str = "Engineer") -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id="6000558004",
        title=title,
        url="https://job-boards.greenhouse.io/tines/jobs/6000558004",
        description="Build things.",
        location_raw="Dublin, Ireland",
        country="IE",
        city="Dublin",
        posted_at=datetime(2026, 5, 20, 0, 17, 51, tzinfo=UTC),
        content_hash="a" * 64,
    )


@pytest.fixture
def company_id(db: sqlite3.Connection) -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2)
    )
    assert company.id is not None
    return company.id


def test_upsert_idempotent(db: sqlite3.Connection, company_id: int) -> None:
    repo = SqliteJobRepo(db)

    repo.upsert(company_id, make_job(), seen_at=FIRST_POLL)
    repo.upsert(company_id, make_job(), seen_at=SECOND_POLL)

    rows = db.execute("SELECT * FROM jobs").fetchall()
    assert len(rows) == 1
    assert rows[0]["first_seen_at"] == FIRST_POLL.isoformat()
    assert rows[0]["last_seen_at"] == SECOND_POLL.isoformat()


def test_upsert_refreshes_mutable_fields(db: sqlite3.Connection, company_id: int) -> None:
    repo = SqliteJobRepo(db)

    repo.upsert(company_id, make_job(title="Engineer"), seen_at=FIRST_POLL)
    repo.upsert(company_id, make_job(title="Senior Engineer"), seen_at=SECOND_POLL)

    rows = db.execute("SELECT title FROM jobs").fetchall()
    assert [row["title"] for row in rows] == ["Senior Engineer"]


def test_upsert_persists_classification(db: sqlite3.Connection, company_id: int) -> None:
    repo = SqliteJobRepo(db)

    repo.upsert(
        company_id,
        make_job(),
        seen_at=FIRST_POLL,
        classification=Classification(frozenset({Category.IOS, Category.AI_ML}), Level.SENIOR),
    )

    row = db.execute("SELECT categories, level FROM jobs").fetchone()
    assert row["categories"] == "ai-ml,ios"
    assert row["level"] == "senior"


def test_content_hash_for_reads_back_stored_hash(db: sqlite3.Connection, company_id: int) -> None:
    repo = SqliteJobRepo(db)

    assert repo.content_hash_for("greenhouse", "6000558004") is None
    repo.upsert(company_id, make_job(), seen_at=FIRST_POLL)
    assert repo.content_hash_for("greenhouse", "6000558004") == "a" * 64


def test_company_upsert_is_idempotent_and_returns_id(db: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(db)
    company = Company(
        name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2
    )

    first = repo.upsert(company)
    second = repo.upsert(company)

    assert first.id is not None and first.id == second.id
    assert db.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"] == 1
