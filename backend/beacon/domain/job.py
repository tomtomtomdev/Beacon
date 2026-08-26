from dataclasses import dataclass
from datetime import datetime

from beacon.domain.classification import Level

# A posting absent from this many consecutive *successful* polls of its source is closed
# (kept, greyed out — SPEC §7). Failed polls never count toward absence.
CLOSE_AFTER_MISSES = 2


@dataclass(frozen=True, slots=True)
class NormalizedJob:
    """A job posting reduced to source-independent form, ready to upsert."""

    source_id: str
    external_id: str
    title: str
    url: str
    description: str
    location_raw: str
    country: str | None
    city: str | None
    posted_at: datetime | None  # aware UTC; None when the board omits it — never fabricated
    content_hash: str
    # Set only by company-less sources (HN/JobTech) that parse the employer from the posting;
    # ATS jobs leave it None (their company comes from the seed row being polled).
    company_name: str | None = None
    # Set only by the boards that publish a seniority of their own (The Muse `levels[]`).
    # The classifier prefers it over its title regex — same precedence as an adapter-provided
    # ISO-2 country beating parse_location. None means "the board said nothing usable",
    # which is not the same as Level.UNSPECIFIED and must not override a title that names one.
    source_level: Level | None = None
