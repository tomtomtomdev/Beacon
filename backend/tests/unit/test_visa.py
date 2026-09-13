"""The country/visa reference data (SPEC §4) is pure domain knowledge — every target
country present, tiers per SPEC §3, and each row carries a verified date + source_url."""

from datetime import date

import pytest

from beacon.domain.visa import COUNTRY_REFERENCE, CountryReference, PriorityTier

BY_CODE: dict[str, CountryReference] = {c.code: c for c in COUNTRY_REFERENCE}

PRIMARY_CODES = {"SG", "AU", "JP", "NL", "US", "CA", "IE"}
NICE_TO_HAVE_CODES = {"SE", "NO", "DK", "CH"}


HOME_CODE = "ID"


def test_all_spec_countries_present_including_the_home_row() -> None:
    assert set(BY_CODE) == PRIMARY_CODES | NICE_TO_HAVE_CODES | {HOME_CODE}


def test_indonesia_is_the_one_home_row() -> None:
    """SPEC §4: Indonesia is listed so the UI can render a market card and a jobs list for it
    like any other — it is the baseline every relocation is measured against, not a target.
    A second home row would be a contradiction, not a new market."""
    assert {c.code for c in COUNTRY_REFERENCE if c.priority_tier is PriorityTier.HOME} == {
        HOME_CODE
    }


def test_home_row_states_the_absent_question_rather_than_empty_fields() -> None:
    """SPEC §4 / DESIGN §1: every relocation field is inapplicable here, and rendering them
    blank or as "n/a" would read as missing data rather than as an absent question. The row
    is also the one whose registry column must never invite a registry lookup — not_required
    comes from the job's location, never from a register."""
    home = BY_CODE[HOME_CODE]

    assert "right to work" in home.visa_summary.lower()
    assert "citizen" in home.pr_summary.lower()
    assert "registry" not in home.registry_name.lower() or "n/a" in home.registry_name.lower()


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
