from dataclasses import dataclass

# ats_type stamped on employers shadowed from a company-less posting (HN/JobTech): no adapter
# polls them, and they're excluded from the source-health view (they aren't pollable sources).
SHADOW_ATS_TYPE = "none"


@dataclass(frozen=True, slots=True)
class Company:
    """A seed company whose ATS board we poll. id is None until persisted.

    registry_flags / match_confidence reflect the last registry refresh; seed rows
    default to 0 / None and never overwrite persisted values on re-seed."""

    name: str
    ats_type: str
    ats_slug: str
    country_hq: str
    priority: int
    id: int | None = None
    registry_flags: int = 0
    match_confidence: float | None = None
