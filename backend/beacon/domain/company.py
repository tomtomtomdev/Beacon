from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Company:
    """A seed company whose ATS board we poll. id is None until persisted."""

    name: str
    ats_type: str
    ats_slug: str
    country_hq: str
    priority: int
    id: int | None = None
