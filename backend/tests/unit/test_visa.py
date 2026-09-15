"""The country/visa reference data (SPEC §4) is pure domain knowledge — every target
country present, tiers per SPEC §3, and each row carries a verified date + source_url."""

import re
from datetime import date
from pathlib import Path

import pytest

from beacon.domain.visa import COUNTRY_REFERENCE, CountryReference, PriorityTier

BY_CODE: dict[str, CountryReference] = {c.code: c for c in COUNTRY_REFERENCE}

PRIMARY_CODES = {"SG", "AU", "JP", "NL", "US", "CA", "IE", "GB"}
NICE_TO_HAVE_CODES = {"SE", "NO", "DK", "CH", "NZ", "TW", "HK"}

# Slice 18 widened §4. These four were verified on their own date against official pages, so
# they must not inherit the table-wide Jan-2026 knowledge date the original twelve share.
SLICE_18_CODES = {"GB", "NZ", "TW", "HK"}


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


@pytest.mark.parametrize("country", COUNTRY_REFERENCE, ids=lambda c: c.code)
def test_no_row_claims_to_be_verified_in_the_future(country: CountryReference) -> None:
    """A future verified_at renders in the UI as "verified as of <date>" — a date that has not
    happened yet is not optimism, it is a lie about reference data (CLAUDE.md data notes)."""
    assert country.verified_at <= date.today()


@pytest.mark.parametrize("code", sorted(SLICE_18_CODES))
def test_slice_18_rows_carry_their_own_verification_date(code: str) -> None:
    """The twelve original rows share SPEC §4's table-wide "as-known Jan 2026" date. A row
    checked in September must say September — inheriting January would backdate research that
    had not been done, which is the one thing verified_at exists to prevent."""
    assert BY_CODE[code].verified_at > date(2026, 1, 15)


def test_uk_registry_points_at_the_register_already_ingested() -> None:
    """The UK register was ingested from slice 2 as a "sponsors somewhere" proxy. With GB a
    target country the same bit now says something stronger — that a GB job's employer sponsors
    *in the country the job is in* — so the row must name it rather than claim none exists."""
    assert "register" in BY_CODE["GB"].registry_name.lower()


def test_new_zealand_registry_states_why_it_cannot_be_ingested() -> None:
    """INZ publishes accredited employers as a daily-updated SEARCH tool with no bulk export,
    and lets employers opt out of appearing. That is not a registry this repo can ingest —
    scraping it is out of scope by the cross-cutting rules — so the row says so plainly rather
    than implying an ingester exists (the Sweden row is the precedent)."""
    registry = BY_CODE["NZ"].registry_name.lower()

    assert "search" in registry
    assert "no bulk export" in registry or "not downloadable" in registry


def test_taiwan_names_the_self_sponsored_card_in_its_visa_copy() -> None:
    """The Gold Card carries its own work permit, so TW needs no sponsoring employer. That
    fact belongs in the visa copy and NOWHERE else: `not_required` is a location predicate for
    the home market only, and a second one in resolve_tier would break the single-source tier
    chain (CLAUDE.md). This test is the reminder of where the fact is allowed to live."""
    assert "self-sponsored" in BY_CODE["TW"].visa_summary.lower()


def test_hong_kong_states_permanent_residency_is_the_endpoint() -> None:
    """There is no separate HK citizenship — nationality is a PRC matter, and right of abode
    after 7 years is the real endpoint. SPEC §4 distinguishes PR from citizenship precisely so
    a market like this can be honest instead of leaving the column vague."""
    citizenship = BY_CODE["HK"].citizenship_summary.lower()

    assert "no separate" in citizenship or "none" in citizenship


def test_every_country_has_a_globe_pin() -> None:
    """A country row with no PIN_GEO entry is dropped from the globe SILENTLY — Globe.tsx
    guards the lookup with a ternary, so the market renders in the card stack and the filter
    menu and simply never appears on the map. Nothing fails; it is just quietly missing.

    This is the one guard that has to cross stacks: COUNTRY_REFERENCE lives in the domain and
    PIN_GEO lives in the frontend, and no single-stack test can see both. Reading the TS file
    is deliberate — a brittle path that fails loudly beats a silent hole in the map."""
    globe_geo = Path(__file__).parents[3] / "frontend/src/countries/globeGeo.ts"
    # Split on "= {" then the closing "\n}": the declaration's own type annotation
    # ({ lat: number; lon: number }) contains braces, so naive brace-splitting reads nothing.
    body = globe_geo.read_text().split("export const PIN_GEO")[1].split("= {", 1)[1]
    pinned = set(re.findall(r"^  ([A-Z]{2}):", body.split("\n}")[0], re.MULTILINE))

    assert pinned, "no PIN_GEO entries parsed — the guard would pass vacuously"

    assert {c.code for c in COUNTRY_REFERENCE} <= pinned
