"""Registry ingesters parse recorded snapshots (fixtures) into RegistryCompany rows.
Every hazard listed in PLAN slice 2 for each register is asserted here."""

from pathlib import Path

from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.domain.matching import match_confidence
from beacon.domain.registry import Registry

REGISTRIES = Path(__file__).parents[1] / "fixtures" / "registries"
UK_FIXTURE = REGISTRIES / "uk_sponsors_fixture.csv"
IND_FIXTURE = REGISTRIES / "ind_sponsors_fixture.csv"
H1B_FIXTURE = REGISTRIES / "h1b_lca_fixture.csv"


# ── UK Home Office register ──────────────────────────────────────────────────────
def test_uk_ingester_declares_uk_registry() -> None:
    assert UKSponsorRegistry(UK_FIXTURE).registry is Registry.UK


def test_uk_parse_strips_whitespace_dedupes_routes_and_survives_crlf() -> None:
    companies = UKSponsorRegistry(UK_FIXTURE).fetch()

    # 35 data rows, but "Spotify Limited" appears twice (one row per visa route).
    assert len(companies) == 34
    assert all(c.name == c.name.strip() for c in companies)
    names = {c.name for c in companies}
    assert "CANVA UK OPERATIONS LIMITED" in names  # trailing space stripped
    assert "Asian African Foods Ltd" in names  # leading + trailing stripped


def test_uk_trading_as_is_parsed_into_an_alias() -> None:
    companies = UKSponsorRegistry(UK_FIXTURE).fetch()

    agilebits = next(c for c in companies if c.name.startswith("AgileBits"))
    assert agilebits.name == "AgileBits UK Ltd"
    assert agilebits.aliases == ("1Password",)
    assert match_confidence("1Password", agilebits) is not None


# ── NL IND recognised-sponsors register ──────────────────────────────────────────
def test_ind_ingester_declares_nl_registry() -> None:
    assert INDRegistry(IND_FIXTURE).registry is Registry.NL


def test_ind_keeps_every_entity_with_kvk_evidence() -> None:
    companies = INDRegistry(IND_FIXTURE).fetch()

    # Multi-entity companies (Backbase ×3, Adyen ×2, …) are all kept; counting once
    # happens at match time, not at parse time.
    assert len(companies) == 25
    assert sum(1 for c in companies if c.name.startswith("Backbase")) == 3
    messagebird = next(c for c in companies if c.name == "Messagebird B.V.")
    assert "51874474" in messagebird.evidence  # KvK number preserved as evidence


# ── US H-1B LCA disclosure file ───────────────────────────────────────────────────
def test_h1b_ingester_declares_us_registry() -> None:
    assert H1BLCARegistry(H1B_FIXTURE).registry is Registry.US


def test_h1b_counts_only_certified_and_skips_padding_rows() -> None:
    companies = H1BLCARegistry(H1B_FIXTURE).fetch()

    # 36 unique certified employers; "Stripe, LLC" spans 2 rows → 1 employer.
    # Denied/Withdrawn rows and the empty padding row contribute nothing.
    assert len(companies) == 36
    figma = next(c for c in companies if c.name.startswith("Figma"))
    assert figma.evidence == "1 certified LCA filing"  # Denied row excluded
    stripe = next(c for c in companies if c.name.startswith("Stripe"))
    assert stripe.evidence == "2 certified LCA filings"


def test_h1b_dba_from_name_and_column_become_aliases() -> None:
    companies = H1BLCARegistry(H1B_FIXTURE).fetch()

    miro = next(c for c in companies if c.name.startswith("RealTimeBoard"))
    assert "Miro" in miro.aliases  # embedded "dba Miro" in EMPLOYER_NAME
    assert match_confidence("Miro", miro) is not None
    assert match_confidence("Miro", next(c for c in companies if c.name == "Mirova US LLC")) is None

    tek = next(c for c in companies if c.name.startswith("Tek Ninjas Solutions"))
    assert "Tek Ninjas" in tek.aliases  # separate TRADE_NAME_DBA column
