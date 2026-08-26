"""Registry ingesters parse recorded snapshots (fixtures) into RegistryCompany rows.
Every hazard listed in PLAN slice 2 for each register is asserted here."""

from pathlib import Path

import pytest

from beacon.adapters.registries.ca import CALMIARegistry
from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ie import IEPermitsRegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.domain.matching import match_confidence
from beacon.domain.registry import Registry

REGISTRIES = Path(__file__).parents[1] / "fixtures" / "registries"
UK_FIXTURE = REGISTRIES / "uk_sponsors_fixture.csv"
IND_FIXTURE = REGISTRIES / "ind_sponsors_fixture.csv"
H1B_FIXTURE = REGISTRIES / "h1b_lca_fixture.csv"
IE_FIXTURE = REGISTRIES / "ie_permits_fixture.csv"
CA_FIXTURE = REGISTRIES / "ca_lmia_fixture.csv"


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


# ── IE DETE employment-permits register ──────────────────────────────────────────
def test_ie_ingester_declares_ie_registry() -> None:
    assert IEPermitsRegistry(IE_FIXTURE).registry is Registry.IE


def test_ie_parses_one_employer_per_row_and_skips_export_padding() -> None:
    companies = IEPermitsRegistry(IE_FIXTURE).fetch()

    # 18 data rows, one of them the empty row an Excel export leaves behind.
    assert len(companies) == 17
    names = {c.name for c in companies}
    assert "KIRAT GOURMET FOOD LIMITED" in names  # leading space in the published name
    assert all(c.name == c.name.strip() for c in companies)


def test_ie_evidence_counts_the_permits_the_year_issued() -> None:
    companies = IEPermitsRegistry(IE_FIXTURE).fetch()

    anthropic = next(c for c in companies if c.name.startswith("Anthropic"))
    stripe = next(c for c in companies if c.name.startswith("Stripe"))
    assert anthropic.evidence == "1 employment permit issued"
    assert stripe.evidence == "57 employment permits issued"


def test_ie_trading_as_is_parsed_into_an_alias() -> None:
    companies = IEPermitsRegistry(IE_FIXTURE).fetch()

    ardrar = next(c for c in companies if c.name.startswith("Ardrar"))
    assert ardrar.name == "Ardrar Ltd."
    assert ardrar.aliases == ("Swyft Energy",)
    assert match_confidence("Swyft Energy", ardrar) is not None


def test_ie_matches_a_seeded_irish_employer() -> None:
    companies = IEPermitsRegistry(IE_FIXTURE).fetch()

    openai = next(c for c in companies if c.name.startswith("OpenAI"))
    assert match_confidence("OpenAI", openai) is not None


# ── CA TFWP positive-LMIA employers list ─────────────────────────────────────────
def test_ca_ingester_declares_ca_registry() -> None:
    assert CALMIARegistry(CA_FIXTURE).registry is Registry.CA


def test_ca_reads_past_the_title_banner_and_ignores_the_footnotes() -> None:
    companies = CALMIARegistry(CA_FIXTURE).fetch()

    # The export opens with a one-cell title sentence and closes with a "Notes:" block;
    # neither is a row, and 21 data rows carry 9 distinct employers.
    assert len(companies) == 9
    assert not any("Notes" in c.name or "LMIA System" in c.name for c in companies)


def test_ca_aggregates_filings_per_employer_across_streams() -> None:
    companies = CALMIARegistry(CA_FIXTURE).fetch()

    # One row per (stream, occupation): a large sponsor must not read like a one-filing shop.
    amazon = next(c for c in companies if c.name.startswith("Amazon"))
    shopify = next(c for c in companies if c.name.startswith("Shopify"))
    cohere = next(c for c in companies if c.name.startswith("Cohere"))
    assert amazon.evidence == "10 positive LMIAs (10 positions)"
    assert shopify.evidence == "3 positive LMIAs (3 positions)"
    assert cohere.evidence == "1 positive LMIA (1 position)"


def test_ca_counts_positions_separately_from_lmias() -> None:
    companies = CALMIARegistry(CA_FIXTURE).fetch()

    # 2+4+13 LMIAs covering 4+5+751 positions — one LMIA can approve many positions.
    fruits = next(c for c in companies if c.name.startswith("Jealous"))
    assert fruits.evidence == "19 positive LMIAs (760 positions)"


def test_ca_matches_a_seeded_canadian_employer() -> None:
    companies = CALMIARegistry(CA_FIXTURE).fetch()

    cohere = next(c for c in companies if c.name.startswith("Cohere"))
    assert match_confidence("Cohere", cohere) == 1.0


def test_ca_unreadable_snapshot_fails_loudly(tmp_path: Path) -> None:
    """A snapshot whose header we cannot find must raise, not yield rows keyed on junk —
    silently matching nothing would read as "no Canadian sponsors exist"."""
    broken = tmp_path / "ca_lmia.csv"
    broken.write_text("Some other export entirely\nfoo,bar\n1,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no header row containing 'Employer'"):
        CALMIARegistry(broken).fetch()
