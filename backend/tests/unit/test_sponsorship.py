import pytest

from beacon.domain.registry import Registry
from beacon.domain.sponsorship import SponsorTier, resolve_tier, tier_sort_rank


@pytest.mark.parametrize(
    ("text_tier", "registry_flags", "expected"),
    [
        # Slice 2: no text classifier yet, so text_tier is None; registry drives the tier.
        (None, 0, SponsorTier.UNKNOWN),
        (None, int(Registry.UK), SponsorTier.REGISTRY_INFERRED),
        (None, int(Registry.NL | Registry.US), SponsorTier.REGISTRY_INFERRED),
        (None, int(Registry.MANUAL), SponsorTier.REGISTRY_INFERRED),
        # Precedence (CLAUDE.md): explicit text beats registry, no beats yes.
        (SponsorTier.EXPLICIT_YES, 0, SponsorTier.EXPLICIT_YES),
        (SponsorTier.EXPLICIT_YES, int(Registry.UK), SponsorTier.EXPLICIT_YES),
        (SponsorTier.EXPLICIT_NO, int(Registry.UK), SponsorTier.EXPLICIT_NO),
    ],
    ids=[
        "no-flags-unknown",
        "uk-flag-registry_inferred",
        "multi-flag-registry_inferred",
        "manual-flag-registry_inferred",
        "explicit_yes-no-flags",
        "explicit_yes-beats-registry",
        "explicit_no-beats-registry",
    ],
)
def test_resolve_tier(
    text_tier: SponsorTier | None, registry_flags: int, expected: SponsorTier
) -> None:
    assert resolve_tier(text_tier, registry_flags) == expected


def test_tier_sort_rank_matches_domain_table() -> None:
    assert tier_sort_rank(SponsorTier.EXPLICIT_YES) == 3
    assert tier_sort_rank(SponsorTier.REGISTRY_INFERRED) == 2
    assert tier_sort_rank(SponsorTier.UNKNOWN) == 1
    assert tier_sort_rank(SponsorTier.EXPLICIT_NO) == 0
