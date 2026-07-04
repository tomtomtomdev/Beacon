"""Parse ATS location strings into (country_code, city).

Conservative by design: a country is only reported when the string names one
(or a US state); nothing is ever fabricated. The raw string is preserved on
the job row, so a better parser can re-parse without re-fetching.
"""

import re

from beacon.domain.countries import COUNTRY_NAME_TO_CODE, REGION_TOKENS, US_STATE_CODES

_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")


def parse_location(raw: str) -> tuple[str | None, str | None]:
    cleaned = _PARENTHETICAL.sub("", raw).strip()
    if not cleaned:
        return None, None

    segments = [s for s in (seg.strip() for seg in cleaned.split(",")) if s]
    if not segments:
        return None, None

    if len(segments) == 1:
        return _parse_single_segment(segments[0])

    first, last = segments[0], segments[-1]
    country = _country_code(last)
    if country is not None:
        city = None if _country_code(first) == country else first
        return country, city
    if last.upper() in US_STATE_CODES:
        return "US", first
    return None, None


def _parse_single_segment(segment: str) -> tuple[str | None, str | None]:
    country = _country_code(segment)
    if country is not None:
        return country, None
    if segment.casefold() in REGION_TOKENS or " or " in segment.casefold():
        return None, None
    return None, segment


def _country_code(segment: str) -> str | None:
    key = segment.casefold()
    if key in COUNTRY_NAME_TO_CODE:
        return COUNTRY_NAME_TO_CODE[key]
    # "United States - East" → the part before the dash names the country.
    head = key.split(" - ")[0].strip()
    return COUNTRY_NAME_TO_CODE.get(head)
