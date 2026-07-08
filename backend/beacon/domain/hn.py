"""Parse a Hacker News "Who is hiring?" top-level comment into a job posting.

Pure domain logic. The monthly thread follows a loose convention: each top-level
comment opens with a header line ``Company | Location | Role | …`` (fields in any
order, often with extras like employment type, tech stack or a URL), and the body
follows after a paragraph break. We extract the header — the first paragraph — and
pull out the company (always the first field), plus a best-effort location and role.

The heuristic is deliberately conservative: absence of a structured header returns
None (skip it) rather than fabricating a posting. Role/location keyword tables are
DATA below; spot-check misses become new rows, never bespoke logic.
"""

import re
from dataclasses import dataclass

from beacon.domain.descriptions import normalize_description
from beacon.domain.location import parse_location

# HN separates paragraphs with <p>; the header is everything before the first one.
_PARA_BREAK = re.compile(r"<p\b[^>]*>|\n")

# Words that mark a header field as a role/title rather than a location or extra.
_ROLE_KEYWORDS = (
    "engineer",
    "engineering",
    "developer",
    "dev",
    "programmer",
    "sre",
    "devops",
    "architect",
    "designer",
    "scientist",
    "researcher",
    "analyst",
    "manager",
    "lead",
    "director",
    "founder",
    "intern",
    "consultant",
    "administrator",
    "specialist",
    "technician",
    "recruiter",
    "head of",
    "vp",
    "cto",
    "ceo",
    "staff",
    "principal",
    "full-stack",
    "fullstack",
    "frontend",
    "backend",
    "front-end",
    "back-end",
)
_ROLE_RE = re.compile(r"\b(?:" + "|".join(_ROLE_KEYWORDS) + r")\b", re.IGNORECASE)

# Signals that a field describes where the work happens even when no country is named.
_LOCATION_SIGNALS = ("remote", "hybrid", "onsite", "on-site", "on site")


@dataclass(frozen=True, slots=True)
class HnPosting:
    """A parsed Who-is-hiring header. company is always present; the rest is best-effort."""

    company: str
    location: str | None
    role: str | None


def parse_hn_posting(text: str) -> HnPosting | None:
    """The header fields of a Who-is-hiring comment, or None if it isn't a structured posting."""
    header = next(
        (h for h in (normalize_description(chunk) for chunk in _PARA_BREAK.split(text)) if h), ""
    )
    parts = [part.strip() for part in header.split("|") if part.strip()]
    if len(parts) < 2:
        return None

    company, *rest = parts
    return HnPosting(company=company, location=_first_location(rest), role=_first_role(rest))


def _first_role(fields: list[str]) -> str | None:
    return next((field for field in fields if _ROLE_RE.search(field)), None)


def _first_location(fields: list[str]) -> str | None:
    for field in fields:
        if parse_location(field)[0] is not None:
            return field
    lowered = [(field, field.casefold()) for field in fields]
    return next(
        (field for field, low in lowered if any(sig in low for sig in _LOCATION_SIGNALS)),
        None,
    )
