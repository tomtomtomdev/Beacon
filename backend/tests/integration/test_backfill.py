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
from beacon.application.backfill import (
    backfill_classifications,
    upgrade_ambiguous_classifications,
)
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


EMPTY = Classification(frozenset(), Level.UNSPECIFIED)


class ResolvingClassifier:
    """Stands in for the LLM-backed tiered classifier: resolves the residue it can (by
    external_id), leaves the rest empty. Never touches the network."""

    def __init__(self, resolved: dict[str, Classification]) -> None:
        self._resolved = resolved

    def classify(self, job: NormalizedJob) -> Classification:
        return self._resolved.get(job.external_id, EMPTY)


def test_upgrade_reclassifies_only_the_empty_category_residue(
    db: sqlite3.Connection, company_id: int
) -> None:
    repo = SqliteJobRepo(db)
    # A already has a category (not residue); B and C are classified-empty ("").
    repo.upsert(
        company_id,
        _job("A", "iOS Engineer", "Swift"),
        seen_at=POLL,
        classification=Classification(frozenset({Category.IOS}), Level.SENIOR),
    )
    repo.upsert(
        company_id, _job("B", "Research Engineer", "..."), seen_at=POLL, classification=EMPTY
    )
    repo.upsert(company_id, _job("C", "Program Manager", "..."), seen_at=POLL, classification=EMPTY)

    upgraded = upgrade_ambiguous_classifications(
        repo, ResolvingClassifier({"B": Classification(frozenset({Category.AI_ML}), Level.STAFF)})
    )

    assert upgraded == 1  # only B was resolved; C stayed empty and is not counted
    rows = {
        row["external_id"]: (row["categories"], row["level"])
        for row in db.execute("SELECT external_id, categories, level FROM jobs")
    }
    assert rows["A"] == ("ios", "senior")  # not residue → untouched
    assert rows["B"] == ("ai-ml", "staff")  # residue resolved by the LLM
    assert rows["C"] == ("", "unspecified")  # residue the LLM could not resolve → left as-is


def test_upgrade_ignores_never_classified_rows(db: sqlite3.Connection, company_id: int) -> None:
    repo = SqliteJobRepo(db)
    repo.upsert(company_id, _job("D", "Software Engineer", "..."), seen_at=POLL)  # categories NULL

    upgraded = upgrade_ambiguous_classifications(
        repo,
        ResolvingClassifier({"D": Classification(frozenset({Category.BACKEND}), Level.SENIOR)}),
    )

    assert upgraded == 0  # NULL is 'never classified', not the empty residue
    row = db.execute("SELECT categories FROM jobs WHERE external_id = 'D'").fetchone()
    assert row["categories"] is None
