"""SqliteCountryRepo seeds and reads the country reference table (real migrations)."""

import sqlite3
from dataclasses import replace
from datetime import date

from beacon.adapters.persistence.countries import SqliteCountryRepo
from beacon.application.countries import list_countries, seed_countries
from beacon.domain.visa import COUNTRY_REFERENCE, CountryReference, PriorityTier


def test_get_all_is_empty_before_seeding(db: sqlite3.Connection) -> None:
    assert SqliteCountryRepo(db).get_all() == []


def test_seed_then_get_all_roundtrips_every_row(db: sqlite3.Connection) -> None:
    repo = SqliteCountryRepo(db)

    seed_countries(repo)

    stored = {c.code: c for c in list_countries(repo)}
    assert stored == {c.code: c for c in COUNTRY_REFERENCE}


def test_get_all_orders_primary_tier_before_nice_to_have(db: sqlite3.Connection) -> None:
    repo = SqliteCountryRepo(db)
    seed_countries(repo)

    tiers = [c.priority_tier for c in repo.get_all()]

    first_nice = tiers.index(PriorityTier.NICE_TO_HAVE)
    assert PriorityTier.PRIMARY not in tiers[first_nice:]


def test_seed_is_idempotent(db: sqlite3.Connection) -> None:
    repo = SqliteCountryRepo(db)

    seed_countries(repo)
    seed_countries(repo)

    assert len(repo.get_all()) == len(COUNTRY_REFERENCE)


def test_reseeding_updates_a_changed_row(db: sqlite3.Connection) -> None:
    repo = SqliteCountryRepo(db)
    original = CountryReference(
        code="SG",
        name="Singapore",
        visa_summary="old",
        pr_summary="p",
        citizenship_summary="c",
        registry_name="r",
        priority_tier=PriorityTier.PRIMARY,
        verified_at=date(2026, 1, 1),
        source_url="https://example.test",
    )
    repo.seed([original])

    repo.seed([replace(original, visa_summary="new")])

    (stored,) = repo.get_all()
    assert stored.visa_summary == "new"
