"""The highest-risk correctness area (CLAUDE.md). Every real-register hazard from
PLAN slice 2 is a row here. Misclassifications found in spot-checks become new rows;
this table is append-only.
"""

import pytest

from beacon.domain.matching import (
    dropped_tokens,
    match_company,
    match_confidence,
    normalize_name,
    registry_matches,
    seed_name_variants,
    split_trading_as,
)
from beacon.domain.registry import Registry, RegistryCompany


# ── Normalization: legal-suffix and casing variants collapse to one key ──────────
@pytest.mark.parametrize(
    ("raw", "expected_key"),
    [
        ("Spotify Limited", {"spotify"}),
        ("Spotify AB", {"spotify"}),
        ("SPOTIFY LTD", {"spotify"}),
        ("Spotify Technology S.A.", {"spotify"}),
        ("Spotify Netherlands B.V.", {"spotify"}),
        ("Robinhood U.K Ltd.", {"robinhood"}),  # one-dot punctuation chaos
        ("Backbase U.S.A. Inc.", {"backbase"}),  # dotted geo abbreviation
        ("AGODA INTERNATIONAL PTE LTD", {"agoda"}),
        ("Anthropic, PBC", {"anthropic"}),  # PBC suffix
        ("OpenAI OpCo, LLC", {"openai"}),  # OpCo divisional token
        ("Plaid, B.V.", {"plaid"}),  # comma before suffix
        ("Databricks", {"databricks"}),  # bare, no suffix at all
        ("180 Amsterdam BV", {"180"}),  # BV without dots + city token
        ("Wetransfer B.V.", {"wetransfer"}),  # casefold, not lower
        # Irish legal forms, appended with the IE register (slice 14). Ireland writes
        # "Unlimited Company"/"Designated Activity Company" in full and abbreviates them
        # UC/DAC, so without these an Irish subsidiary keeps its legal form as a
        # distinctive token and never matches its own brand.
        ("Analog Devices International Unlimited Company", {"analog", "devices"}),
        ("Stripe Technology Company Limited", {"stripe"}),
        ("Gilead Sciences Ireland UC", {"gilead", "sciences"}),
        ("Azimut Life dac", {"azimut", "life"}),
        ("Compass Residential Designated Activity Company", {"compass", "residential"}),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else "",
)
def test_name_normalization_collapses_variants(raw: str, expected_key: set[str]) -> None:
    assert normalize_name(raw).key == frozenset(expected_key)


# ── Confidence gradient ──────────────────────────────────────────────────────────
def test_exact_normalized_match_is_full_confidence() -> None:
    assert match_confidence("Spotify", RegistryCompany("Spotify Limited")) == 1.0


def test_geo_or_structural_stripping_lowers_confidence_but_still_matches() -> None:
    conf = match_confidence("Cohere", RegistryCompany("Cohere US, Inc."))

    assert conf is not None
    assert conf == pytest.approx(0.9)


# ── The Cohere problem: equal token sets, not mere overlap ────────────────────────
def test_extra_distinctive_tokens_block_match() -> None:
    assert match_confidence("Cohere", RegistryCompany("Cohere US, Inc.")) is not None
    assert match_confidence("Cohere", RegistryCompany("Cohere Health, Inc.")) is None


# ── False-positive traps: none may match their similarly-named seed ───────────────
@pytest.mark.parametrize(
    ("seed", "registry_name"),
    [
        ("Stripe", "STRIPE CONSULTING LIMITED"),
        ("Stripe", "Stripe Partners"),
        ("Stripe", "Silverstripe Advisors Ltd"),
        ("Notion", "Notion Capital Managers LLP"),
        ("Linear", "Linear Investments Limited"),
        ("Linear", "Maxlinear, Inc."),
        ("Grab", "GRAB + GO LTD"),
        ("Grab", "Grab Minds, Inc."),
        ("Miro", "CAFE MIRO LIMITED"),
        ("Miro", "Mirova US LLC"),
        ("Canva", "Blank Canvas"),
        ("Canva", "Mental Canvas, Inc."),
        ("Cohere", "Coherence Neuro Limited"),
    ],
    ids=lambda v: v.replace(" ", "_"),
)
def test_false_positive_traps_never_match(seed: str, registry_name: str) -> None:
    assert match_confidence(seed, RegistryCompany(registry_name)) is None


# ── Token-boundary, never substring ───────────────────────────────────────────────
@pytest.mark.parametrize(
    ("seed", "registry_name"),
    [
        ("Reddit", "Redditch Care Ltd"),  # Reddit ⊂ Redditch
        ("Adyen", "Gradyent B.V."),  # Adyen ⊂ Gradyent
        ("Grab", "Grabowsky B.V."),  # Grab ⊂ Grabowsky
    ],
    ids=["reddit-redditch", "adyen-gradyent", "grab-grabowsky"],
)
def test_substring_is_not_a_match(seed: str, registry_name: str) -> None:
    assert match_confidence(seed, RegistryCompany(registry_name)) is None


# ── Real subsidiaries that need geo/structural stripping still match ──────────────
@pytest.mark.parametrize(
    ("seed", "registry_name"),
    [
        ("Atlassian", "Atlassian (UK) Operations Limited"),
        ("Intercom", "Intercom Software UK Limited"),
        ("Canva", "CANVA UK OPERATIONS LIMITED "),  # trailing space
        ("Plaid", "Plaid Financial Ltd"),
        ("Miro", "Miro EMEA UK Ltd."),
        ("Stripe", "Stripe Payments UK Ltd"),
        ("Adyen", "ADYEN N.V. LONDON BRANCH"),
        ("Picnic", "Picnic Technologies B.V."),
        ("Robinhood", "Robinhood Markets, Inc."),
        ("Faire", "Faire Wholesale, Inc."),
        ("Notion", "Notion Labs, Inc."),
    ],
    ids=lambda v: v.replace(" ", "_").replace(".", ""),
)
def test_real_subsidiaries_match(seed: str, registry_name: str) -> None:
    assert match_confidence(seed, RegistryCompany(registry_name)) is not None


# ── Trading-as / dba: legal name shares no tokens with the brand ──────────────────
def test_trading_as_extraction() -> None:
    legal, aliases = split_trading_as("AgileBits UK Ltd trading as 1Password")

    assert legal == "AgileBits UK Ltd"
    assert aliases == ("1Password",)


def test_trading_as_alias_matches_seed() -> None:
    entry = RegistryCompany(name="AgileBits UK Ltd", aliases=("1Password",))

    assert match_confidence("1Password", entry) is not None


def test_dba_extraction_and_matching() -> None:
    legal, aliases = split_trading_as("RealTimeBoard, Inc. dba Miro")

    assert (legal, aliases) == ("RealTimeBoard, Inc.", ("Miro",))
    assert match_confidence("Miro", RegistryCompany(legal, aliases=aliases)) is not None


def test_split_trading_as_passthrough_when_absent() -> None:
    assert split_trading_as("Spotify Limited") == ("Spotify Limited", ())


# ── Parenthetical aliases on seed names ───────────────────────────────────────────
def test_seed_parenthetical_becomes_an_alias_variant() -> None:
    assert seed_name_variants("Bird (MessageBird)") == ("Bird", "MessageBird")


@pytest.mark.parametrize(
    ("seed", "variants"),
    [
        # Singapore shorthand in MyCareersFuture employer names (slice 25b): geography, not a
        # brand. "(S)" alone matched PERM's "Group-S LLC" for two unrelated companies.
        ("GMP RECRUITMENT SERVICES (S) PTE LTD", ("GMP RECRUITMENT SERVICES  PTE LTD",)),
        ("TRAINOCATE (S) PTE. LTD.", ("TRAINOCATE  PTE. LTD.",)),
        ("SEATRIUM (SG) PTE. LTD.", ("SEATRIUM  PTE. LTD.",)),
        ("AIRWALLEX (SINGAPORE) PTE. LTD.", ("AIRWALLEX  PTE. LTD.",)),
        # Real aliases stay variants, acronyms included.
        ("American Bureau of Shipping (ABS)", ("American Bureau of Shipping", "ABS")),
        ("Procreate (Savage Interactive)", ("Procreate", "Savage Interactive")),
    ],
    ids=["s", "trainocate-s", "sg", "singapore", "acronym", "legal-name"],
)
def test_geography_and_single_letter_parentheticals_are_not_variants(
    seed: str, variants: tuple[str, ...]
) -> None:
    assert seed_name_variants(seed) == variants


def test_parenthetical_alias_matching() -> None:
    assert match_confidence("Bird (MessageBird)", RegistryCompany("Messagebird B.V.")) is not None
    assert match_confidence("Bird (MessageBird)", RegistryCompany("Q*BIRD B.V.")) is None


# ── Spot-check support (slice 25a): per-registry matches, and why a match was stripped ──
COHERE_TECH = RegistryCompany(name="Cohere Technologies Inc.", evidence="1 certified PERM filing")
COHERE_US = RegistryCompany(name="Cohere US, Inc.", evidence="3 certified LCA filings")


def test_registry_matches_reports_the_best_entry_per_registry() -> None:
    entries = {Registry.US: [COHERE_US], Registry.PERM: [COHERE_TECH]}

    matches = registry_matches("Cohere", entries)

    assert [(m.registry, m.entry.name, m.confidence) for m in matches] == [
        (Registry.US, "Cohere US, Inc.", 0.9),
        (Registry.PERM, "Cohere Technologies Inc.", 0.9),
    ]


def test_match_company_is_the_fold_of_registry_matches() -> None:
    entries = {Registry.US: [COHERE_US], Registry.PERM: [COHERE_TECH]}

    result = match_company("Cohere", entries)

    assert result.flags == Registry.US | Registry.PERM
    assert result.evidence == "US 3 certified LCA filings; PERM 1 certified PERM filing"


@pytest.mark.parametrize(
    ("seed", "entry", "dropped"),
    [
        ("Cohere", "Cohere Technologies Inc.", {"technologies"}),  # structural: review it
        ("Backbase", "Backbase U.S.A. Inc.", {"usa"}),  # geography: the safe kind
        ("Stripe", "Stripe, Inc.", set()),  # suffix-only: a full-confidence hit
    ],
    ids=["structural", "geography", "suffix-only"],
)
def test_dropped_tokens_name_what_stripping_removed(
    seed: str, entry: str, dropped: set[str]
) -> None:
    assert dropped_tokens(seed, RegistryCompany(name=entry)) == frozenset(dropped)
