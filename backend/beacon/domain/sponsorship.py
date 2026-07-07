"""Sponsorship tiers. The precedence/sort tables here are the single source of truth."""

from enum import StrEnum
from types import MappingProxyType


class SponsorTier(StrEnum):
    EXPLICIT_YES = "explicit_yes"
    REGISTRY_INFERRED = "registry_inferred"
    UNKNOWN = "unknown"
    EXPLICIT_NO = "explicit_no"


# Drives /jobs default ordering (sort_rank DESC, posted_at DESC). A soft signal:
# explicit_no sorts last but is never hidden, and no tier ever filters by default.
SORT_RANK: MappingProxyType[SponsorTier, int] = MappingProxyType(
    {
        SponsorTier.EXPLICIT_YES: 3,
        SponsorTier.REGISTRY_INFERRED: 2,
        SponsorTier.UNKNOWN: 1,
        SponsorTier.EXPLICIT_NO: 0,
    }
)


def resolve_tier(text_tier: SponsorTier | None, registry_flags: int) -> SponsorTier:
    """The one place tier precedence lives: explicit text beats registry beats unknown.

    text_tier is the posting-text signal (explicit_yes/explicit_no or None until the
    slice-6 classifier lands). registry_flags is the company's registry bitmask.
    """
    if text_tier in (SponsorTier.EXPLICIT_NO, SponsorTier.EXPLICIT_YES):
        return text_tier
    return SponsorTier.REGISTRY_INFERRED if registry_flags else SponsorTier.UNKNOWN


def tier_sort_rank(tier: SponsorTier) -> int:
    return SORT_RANK[tier]
