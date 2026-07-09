"""The country/visa reference data (SPEC §4) is pure domain knowledge — every target
country present, tiers per SPEC §3, and each row carries a verified date + source_url."""

from datetime import date

import pytest

from beacon.domain.visa import COUNTRY_REFERENCE, CountryReference, PriorityTier

BY_CODE: dict[str, CountryReference] = {c.code: c for c in COUNTRY_REFERENCE}

PRIMARY_CODES = {"SG", "AU", "JP", "NL", "US", "CA", "IE"}
NICE_TO_HAVE_CODES = {"SE", "NO", "DK", "CH"}


def test_all_eleven_spec_countries_present() -> None:
    assert set(BY_CODE) == PRIMARY_CODES | NICE_TO_HAVE_CODES


def test_codes_are_unique() -> None:
    codes = [c.code for c in COUNTRY_REFERENCE]
    assert len(codes) == len(set(codes))


def test_primary_countries_are_tier_primary() -> None:
    assert {c.code for c in COUNTRY_REFERENCE if c.priority_tier is PriorityTier.PRIMARY} == (
        PRIMARY_CODES
    )


def test_nice_to_have_countries_are_tier_nice_to_have() -> None:
    assert {
        c.code for c in COUNTRY_REFERENCE if c.priority_tier is PriorityTier.NICE_TO_HAVE
    } == NICE_TO_HAVE_CODES


@pytest.mark.parametrize("country", COUNTRY_REFERENCE, ids=lambda c: c.code)
def test_every_row_is_fully_populated(country: CountryReference) -> None:
    assert country.name
    assert country.visa_summary
    assert country.pr_summary
    assert country.citizenship_summary
    assert country.registry_name
    assert country.source_url.startswith("https://")
    assert isinstance(country.verified_at, date)


def test_sweden_surfaces_the_discontinued_register_note() -> None:
    # SPEC §4 / DESIGN §4: Sweden has no sponsor registry — surface it, never invent one.
    assert "discontinued" in BY_CODE["SE"].registry_name.lower()


def test_sweden_citizenship_carries_the_reform_caveat() -> None:
    # Acceptance: a Swedish job's country card must show the 5yr→8yr reform caveat.
    citizenship = BY_CODE["SE"].citizenship_summary.lower()
    assert "8" in citizenship and "reform" in citizenship
