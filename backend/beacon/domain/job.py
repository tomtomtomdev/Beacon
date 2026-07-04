from dataclasses import dataclass
from datetime import datetime


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
