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
