"""refresh_registries against the real registry fixtures + the delivered seed file.
This is the slice-2 acceptance spot-check, automated: known companies get the right
flags, controls get none, and job tiers follow.
"""

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.adapters.seeds import parse_seed_csv
from beacon.application.flag_sponsor import flag_manual_sponsor
from beacon.application.ports import RegistryIngester
from beacon.application.refresh_registries import refresh_registries
from beacon.domain.job import NormalizedJob
from beacon.domain.registry import Registry
from beacon.domain.sponsorship import SponsorTier

REGISTRIES = Path(__file__).parents[1] / "fixtures" / "registries"
SEED_FILE = Path(__file__).parents[3] / "seeds" / "companies.csv"
NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


def ingesters() -> list[RegistryIngester]:
    return [
        UKSponsorRegistry(REGISTRIES / "uk_sponsors_fixture.csv"),
        INDRegistry(REGISTRIES / "ind_sponsors_fixture.csv"),
        H1BLCARegistry(REGISTRIES / "h1b_lca_fixture.csv"),
    ]


def make_job(external_id: str) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title="Engineer",
        url=f"https://example.test/{external_id}",
        description="Build things.",
        location_raw="",
        country=None,
        city=None,
        posted_at=None,
        content_hash="a" * 64,
    )


@pytest.fixture
def seeded(db: sqlite3.Connection) -> sqlite3.Connection:
    repo = SqliteCompanyRepo(db)
    for company in parse_seed_csv(SEED_FILE.read_text()):
        repo.upsert(company)
    return db


def flags_of(db: sqlite3.Connection, name: str) -> int:
    row = db.execute("SELECT registry_flags FROM companies WHERE name = ?", (name,)).fetchone()
    return int(row["registry_flags"])


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Adyen", Registry.UK | Registry.NL | Registry.US),
        ("Spotify", Registry.UK | Registry.NL | Registry.US),
        ("Stripe", Registry.UK | Registry.NL | Registry.US),
        ("1Password", Registry.UK),  # via "AgileBits UK Ltd trading as 1Password"
        ("Culture Amp", Registry.UK),
        ("Backbase", Registry.NL | Registry.US),
        ("Duolingo", Registry.US),
        ("Reddit", Registry.US),
        ("Wealthsimple", Registry(0)),  # negative control: absent from all registers
        ("Truecaller", Registry(0)),  # negative control
    ],
    ids=lambda v: str(v),
)
def test_refresh_sets_correct_registry_flags(
    seeded: sqlite3.Connection, name: str, expected: Registry
) -> None:
    repo = SqliteCompanyRepo(seeded)

    refresh_registries(repo.list_active(), ingesters(), repo, SqliteJobRepo(seeded))

    assert flags_of(seeded, name) == int(expected)


def test_refresh_records_confidence_and_evidence(seeded: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(seeded)

    refresh_registries(repo.list_active(), ingesters(), repo, SqliteJobRepo(seeded))

    row = seeded.execute(
        "SELECT match_confidence, match_evidence FROM companies WHERE name = 'Adyen'"
    ).fetchone()
    assert row["match_confidence"] is not None
    assert 0.0 < row["match_confidence"] <= 1.0
    assert "NL" in row["match_evidence"]


def test_refresh_reresolves_job_tiers(seeded: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(seeded)
    jobs = SqliteJobRepo(seeded)
    adyen = repo.get_by_name("Adyen")
    wealthsimple = repo.get_by_name("Wealthsimple")
    assert adyen is not None and adyen.id is not None
    assert wealthsimple is not None and wealthsimple.id is not None
    jobs.upsert(adyen.id, make_job("a1"), seen_at=NOW)
    jobs.upsert(wealthsimple.id, make_job("w1"), seen_at=NOW)

    refresh_registries(repo.list_active(), ingesters(), repo, jobs)

    tiers = {
        row["external_id"]: row["sponsor_tier"]
        for row in seeded.execute("SELECT external_id, sponsor_tier FROM jobs")
    }
    assert tiers["a1"] == SponsorTier.REGISTRY_INFERRED.value
    assert tiers["w1"] == SponsorTier.UNKNOWN.value


def test_manual_flag_yields_registry_inferred(seeded: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(seeded)
    jobs = SqliteJobRepo(seeded)
    lovable = repo.get_by_name("Lovable")  # Swedish seed, absent from every register
    assert lovable is not None and lovable.id is not None
    jobs.upsert(lovable.id, make_job("l1"), seen_at=NOW)

    flag_manual_sponsor(repo, jobs, "Lovable", "listed on relocate.me", flagged_on=date(2026, 7, 7))

    row = seeded.execute(
        "SELECT registry_flags, match_confidence, match_evidence FROM companies WHERE name='Lovable'"
    ).fetchone()
    assert Registry(row["registry_flags"]) & Registry.MANUAL
    assert row["match_confidence"] == 1.0
    assert "relocate.me" in row["match_evidence"]
    tier = seeded.execute("SELECT sponsor_tier FROM jobs WHERE external_id = 'l1'").fetchone()[
        "sponsor_tier"
    ]
    assert tier == SponsorTier.REGISTRY_INFERRED.value


def test_refresh_preserves_a_manual_flag(seeded: sqlite3.Connection) -> None:
    repo = SqliteCompanyRepo(seeded)
    jobs = SqliteJobRepo(seeded)
    flag_manual_sponsor(repo, jobs, "Lovable", "listed on relocate.me", flagged_on=date(2026, 7, 7))

    refresh_registries(repo.list_active(), ingesters(), repo, jobs)

    assert Registry(flags_of(seeded, "Lovable")) & Registry.MANUAL
