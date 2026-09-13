"""Invariants that must hold for EVERY sponsorship tier, including ones not yet invented.

Two of them: the one CLAUDE.md calls out explicitly (registry_inferred can never appear on a
company with empty registry_flags), guarded with hypothesis over random flags; and the
exhaustiveness of the per-tier tables downstream of the resolver.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from beacon.domain.classification import Category, Level
from beacon.domain.rationale import build_rationale
from beacon.domain.resume import JobFacts, ResumeProfile, score_match
from beacon.domain.sponsorship import HOME_COUNTRY, SponsorTier, resolve_tier

_ANY_FLAGS = st.integers(min_value=0, max_value=255)
# Countries the pipeline actually carries: a target country, a non-target one, the
# country-less case the remote boards produce, and the home market.
_ANY_COUNTRY = st.sampled_from([None, "SG", "US", "DE", HOME_COUNTRY])
_AWAY_COUNTRY = st.sampled_from([None, "SG", "US", "DE"])


@given(flags=_ANY_FLAGS, country=_ANY_COUNTRY)
def test_registry_inferred_implies_nonzero_flags(flags: int, country: str | None) -> None:
    if resolve_tier(None, flags, country) is SponsorTier.REGISTRY_INFERRED:
        assert flags != 0


@given(
    flags=_ANY_FLAGS,
    text=st.sampled_from([SponsorTier.EXPLICIT_YES, SponsorTier.EXPLICIT_NO]),
    country=_AWAY_COUNTRY,
)
def test_explicit_text_beats_any_registry_flags(
    flags: int, text: SponsorTier, country: str | None
) -> None:
    """Outside the home market. Inside it the location predicate wins before this chain is
    consulted at all — test_not_required_sits_outside_the_text_chain pins that half."""
    assert resolve_tier(text, flags, country) is text


@pytest.mark.parametrize("tier", list(SponsorTier), ids=[tier.value for tier in SponsorTier])
def test_every_tier_scores_and_explains(tier: SponsorTier) -> None:
    """_SPONSOR_TIER_FIT (domain/resume.py) and _SPONSOR_NOTES (domain/rationale.py) are both
    dicts subscripted directly by tier, so a tier added without a row in each raises KeyError
    on the first job that carries it — a crash reached only once real postings resolve to the
    new tier, long after the commit that added it. Parametrized over the enum so the tier
    after this one cannot repeat the omission."""
    profile = ResumeProfile(
        skills=frozenset({"swift", "swiftui"}),
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        years=8,
    )
    job = JobFacts(
        skills=frozenset({"swift"}),
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        country=HOME_COUNTRY if tier is SponsorTier.NOT_REQUIRED else "SG",
        sponsor_tier=tier,
    )

    rationale = build_rationale(profile, job, score_match(profile, job))

    assert rationale.verdict
    assert rationale.sponsor_note
