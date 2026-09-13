"""`python -m beacon.retier` — the one-shot that moves rows ingested before the home market
existed onto the tier the resolver now gives them (slice 15b).

Wiring only: the predicate lives in application/backfill + domain/sponsorship, so what is
asserted here is that the composition root reaches them against a real DB, runs its own
migrations like every other entry point, and reports what it moved.
"""

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.config import Settings
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.sponsorship import HOME_COUNTRY, SponsorTier
from beacon.retier import main

POLL = datetime(2026, 9, 13, 6, 0, tzinfo=UTC)


def _job(external_id: str, country: str) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title="iOS Engineer",
        url=f"https://example.test/{external_id}",
        description="Build things.",
        location_raw="Jakarta",
        country=country,
        city="Jakarta",
        posted_at=None,
        content_hash=external_id * 8,
    )


@pytest.fixture
def seeded_db(db: sqlite3.Connection, tmp_path: Path) -> Path:
    """Two postings — one home-market, one not — in a DB the CLI will open by path."""
    company = SqliteCompanyRepo(db).upsert(
        Company(name="Grab", ats_type="greenhouse", ats_slug="grab", country_hq="SG", priority=1)
    )
    assert company.id is not None
    jobs = SqliteJobRepo(db)
    jobs.upsert(company.id, _job("id1", HOME_COUNTRY), seen_at=POLL)
    jobs.upsert(company.id, replace(_job("sg1", "SG"), city="Singapore"), seen_at=POLL)
    db.close()  # the CLI opens its own connection to the same file
    return tmp_path / "beacon.db"


def test_retier_cli_moves_home_market_rows_and_reports_the_count(
    seeded_db: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        Settings,
        "from_env",
        classmethod(
            lambda cls: Settings(db_path=seeded_db, seeds_path=seeded_db.parent / "companies.csv")
        ),
    )

    exit_code = main([])

    assert exit_code == 0
    assert "retiered=1" in capsys.readouterr().out
    conn = sqlite3.connect(seeded_db)
    conn.row_factory = sqlite3.Row
    tiers = {
        row["external_id"]: row["sponsor_tier"]
        for row in conn.execute("SELECT external_id, sponsor_tier FROM jobs")
    }
    assert tiers == {"id1": SponsorTier.NOT_REQUIRED.value, "sg1": SponsorTier.UNKNOWN.value}
