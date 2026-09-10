"""`python -m beacon.notify` sends the pending digest without polling — the launch and
close dispatches in run.sh. Wiring only: the matching rules live in application/notify,
so what is asserted here is that the composition root reaches them, and that a run with
no new matches sends nothing even when the source-health section has something to say."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.searches import SqliteSearchRepo
from beacon.config import Settings
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.company import Company
from beacon.domain.health import FailureKind, Health, SourceHealth
from beacon.domain.job import NormalizedJob
from beacon.domain.saved_search import SavedSearch, SearchFilters
from beacon.domain.sponsorship import SponsorSignal, SponsorTier
from beacon.notify import dispatch_digest

NOW = datetime(2026, 9, 10, 6, 0, tzinfo=UTC)
LAST_OK = datetime(2026, 8, 1, 6, 0, tzinfo=UTC)


def settings_for(tmp_path: Path) -> Settings:
    """No Telegram creds → the digest resolves to StdoutNotifier, so a dispatch is
    observable through capsys and never touches the network."""
    return Settings(db_path=tmp_path / "beacon.db", seeds_path=tmp_path / "companies.csv")


def seed_company(db: sqlite3.Connection, *, name: str = "Spotify") -> int:
    company = SqliteCompanyRepo(db).upsert(
        Company(name=name, ats_type="lever", ats_slug=name.lower(), country_hq="SE", priority=1)
    )
    assert company.id is not None  # freshly inserted
    return company.id


def seed_matching_job_and_search(db: sqlite3.Connection) -> None:
    SqliteJobRepo(db).upsert(
        seed_company(db),
        NormalizedJob(
            source_id="lever",
            external_id="1",
            title="Senior iOS Engineer",
            url="https://boards.example/1",
            description="Build the iOS app.",
            location_raw="Stockholm",
            country="SE",
            city="Stockholm",
            posted_at=None,
            content_hash="h-1",
        ),
        seen_at=NOW,
        classification=Classification(categories=frozenset({Category.IOS}), level=Level.SENIOR),
        sponsorship=SponsorSignal(SponsorTier.REGISTRY_INFERRED),
    )
    SqliteSearchRepo(db).create(
        SavedSearch(
            name="Senior iOS · SE",
            filters=SearchFilters(countries=("SE",), categories=("ios",), levels=("senior",)),
        )
    )


def quarantine_a_source(db: sqlite3.Connection) -> None:
    SqliteCompanyRepo(db).set_health(
        seed_company(db, name="Crypto"),
        SourceHealth(
            consecutive_failures=3,
            health=Health.QUARANTINED,
            reason=FailureKind.GONE,
            last_success_at=LAST_OK,
        ),
    )


async def test_dispatch_sends_pending_matches_once_and_records_them(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    seed_matching_job_and_search(db)

    first = await dispatch_digest(settings_for(tmp_path), now=NOW)
    second = await dispatch_digest(settings_for(tmp_path), now=NOW)

    assert (first.new_matches, second.new_matches) == (1, 0)


async def test_a_quarantine_with_no_new_matches_sends_nothing(
    db: sqlite3.Connection, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    quarantine_a_source(db)

    result = await dispatch_digest(settings_for(tmp_path), now=NOW)

    assert result.new_matches == 0
    assert capsys.readouterr().out == ""


async def test_health_alerts_ride_a_digest_that_has_matches(
    db: sqlite3.Connection, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    quarantine_a_source(db)
    seed_matching_job_and_search(db)

    await dispatch_digest(settings_for(tmp_path), now=NOW)

    sent = capsys.readouterr().out
    assert "Source health" in sent and "Senior iOS Engineer" in sent
