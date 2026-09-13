"""`python -m beacon.relocate` — the one-shot that re-reads the location string of every
job with no country and writes what the parser now resolves (slice 17c).

Wiring only: the parsing lives in domain/location and the fill rule in
application/backfill, so what is asserted here is that the composition root reaches them
against a real DB, runs its own migrations like every other entry point, and reports what
it moved — including the residue it deliberately did not fill.
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
from beacon.domain.sponsorship import SponsorTier
from beacon.relocate import main

POLL = datetime(2026, 9, 13, 6, 0, tzinfo=UTC)


def _job(external_id: str, location_raw: str) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title="iOS Engineer",
        url=f"https://example.test/{external_id}",
        description="Build things.",
        location_raw=location_raw,
        country=None,
        city=None,
        posted_at=None,
        content_hash=external_id * 8,
    )


@pytest.fixture
def seeded_db(db: sqlite3.Connection, tmp_path: Path) -> Path:
    """Four uncountried postings, one of each shape the run has to distinguish."""
    company = SqliteCompanyRepo(db).upsert(
        Company(
            name="Proton", ats_type="greenhouse", ats_slug="proton", country_hq="CH", priority=2
        )
    )
    assert company.id is not None
    jobs = SqliteJobRepo(db)
    jobs.upsert(company.id, _job("nl1", "Amsterdam"), seen_at=POLL)  # plain fill
    jobs.upsert(company.id, _job("ch1", "Geneva"), seen_at=POLL)  # settled by the CH hq
    jobs.upsert(company.id, _job("id1", "Jakarta"), seen_at=POLL)  # fill, then retier
    jobs.upsert(company.id, _job("no1", "Anywhere in the World"), seen_at=POLL)  # residue
    jobs.upsert(  # already countried by its adapter — must not move
        company.id, replace(_job("sg1", "Anywhere"), country="SG", city="Singapore"), seen_at=POLL
    )
    db.close()  # the CLI opens its own connection to the same file
    return tmp_path / "beacon.db"


def test_relocate_cli_fills_reports_and_retiers(
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
    assert "relocate filled=3 residue=1 retiered=1" in capsys.readouterr().out
    conn = sqlite3.connect(seeded_db)
    conn.row_factory = sqlite3.Row
    rows = {
        row["external_id"]: (row["country"], row["sponsor_tier"])
        for row in conn.execute("SELECT external_id, country, sponsor_tier FROM jobs")
    }
    assert rows == {
        "nl1": ("NL", SponsorTier.UNKNOWN.value),
        "ch1": ("CH", SponsorTier.UNKNOWN.value),
        "id1": ("ID", SponsorTier.NOT_REQUIRED.value),
        "no1": (None, SponsorTier.UNKNOWN.value),
        "sg1": ("SG", SponsorTier.UNKNOWN.value),
    }
