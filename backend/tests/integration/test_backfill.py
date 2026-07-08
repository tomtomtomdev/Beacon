"""Backfill: classify jobs already in the DB that were never classified (categories NULL).

A categories value of "" is an honest "classified, nothing matched" and must NOT be
re-picked; only NULL (never classified) is backfilled.
"""

import sqlite3
from datetime import UTC, datetime

import pytest

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.application.backfill import backfill_classifications
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

POLL = datetime(2026, 7, 4, 6, 0, tzinfo=UTC)


def _job(external_id: str, title: str, description: str) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title=title,
        url=f"https://example.test/{external_id}",
        description=description,
        location_raw="Remote",
        country=None,
        city=None,
        posted_at=None,
        content_hash=external_id * 8,
    )


@pytest.fixture
def company_id(db: sqlite3.Connection) -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2)
    )
    assert company.id is not None
    return company.id


def test_backfill_classifies_only_never_classified_rows(
    db: sqlite3.Connection, company_id: int
) -> None:
    repo = SqliteJobRepo(db)
    repo.upsert(company_id, _job("A", "Senior iOS Engineer", "Swift and SwiftUI"), seen_at=POLL)
    repo.upsert(
        company_id,
        _job("B", "Backend Engineer", "Go and gRPC"),
        seen_at=POLL,
        classification=Classification(frozenset({Category.BACKEND}), Level.LEAD),
    )

    count = backfill_classifications(repo, HeuristicClassifier())

    assert count == 1  # only A was unclassified
    rows = {
        row["external_id"]: (row["categories"], row["level"])
        for row in db.execute("SELECT external_id, categories, level FROM jobs")
    }
    assert rows["A"] == ("ios", "senior")  # backfilled from title/description
    assert rows["B"] == ("backend", "lead")  # already-classified row untouched


def test_backfill_is_idempotent(db: sqlite3.Connection, company_id: int) -> None:
    repo = SqliteJobRepo(db)
    repo.upsert(company_id, _job("C", "Project Manager", "Own the roadmap"), seen_at=POLL)

    first = backfill_classifications(repo, HeuristicClassifier())
    second = backfill_classifications(repo, HeuristicClassifier())

    assert first == 1  # classified-empty ("") is not NULL, so the re-run skips it
    assert second == 0
