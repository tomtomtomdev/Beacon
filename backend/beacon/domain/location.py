"""Parse ATS location strings into (country_code, city).

Conservative by design: a country is only reported when the string names one
(or a US state); nothing is ever fabricated. The raw string is preserved on
the job row, so a better parser can re-parse without re-fetching.

Three shapes, read outermost first, because boards nest them:

    "Berlin, Germany; Munich, Germany"   many locations, separated by ; • |
    "US - San Francisco"                 one location, a ` - ` delimiter form
    "Austin, Texas"                      one location, comma-separated

A many-location string yields a country only when every part that names one names the
*same* one — a job has a single country column, and picking between two is a coin toss,
which is the same rule that stops `posted_at` being invented from relative prose.
"""

import re
from dataclasses import dataclass

from beacon.domain.countries import (
    CITY_TO_COUNTRY,
    COUNTRY_NAME_TO_CODE,
    NON_CITY_TOKENS,
    US_STATE_CODES,
    US_STATE_NAMES,
)


@dataclass(frozen=True, slots=True)
class UncountriedJob:
    """A stored posting whose country column is empty, with everything needed to read its
    location string again: the string itself, kept on the row for exactly this, and the
    employer's home market for the shared-name tie-break."""

    id: int
    location_raw: str
    country_hq: str | None


_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")
_MULTI_SEPARATOR = re.compile(r"\s*[•;|]\s*")
# Spaced only: "Kitchener-Waterloo" and "North Rhine-Westphalia" are single place names.
_DASH_SEPARATOR = re.compile(r"\s+[-–]\s+")

_ISO_CODES: frozenset[str] = frozenset(COUNTRY_NAME_TO_CODE.values())
# CA/DE/ID/IL/IN read as Canada, Germany, Indonesia, Israel and India — and equally as
# California, Delaware, Idaho, Illinois and Indiana. A bare code that collides with a US
# state names nothing on its own, so it resolves no country here.
_UNAMBIGUOUS_ISO_CODES: frozenset[str] = _ISO_CODES - US_STATE_CODES


def parse_location(raw: str, hq: str | None = None) -> tuple[str | None, str | None]:
    """`hq` is the posting company's home market, and it is read for one purpose only: to
    choose between the countries a shared city name can mean. It never supplies a country
    for a place the tables do not know, which would tag every remote req with the
    employer's address."""
    cleaned = _PARENTHETICAL.sub("", raw).strip()
    if not cleaned:
        return None, None

    locations = [part for part in (p.strip() for p in _MULTI_SEPARATOR.split(cleaned)) if part]
    if not locations:
        return None, None
    if len(locations) > 1:
        return _parse_many(locations)
    return _parse_one(locations[0], hq)


def _parse_many(locations: list[str]) -> tuple[str | None, str | None]:
    """Several locations in one string: the country only if they agree, and never a city —
    with more than one on offer, naming one would be a choice the string does not make.

    The parts are read *without* the employer's home market, because it cannot choose
    between two locations listed side by side. Applying it to "Paris; Geneva" resolves the
    Swiss half and leaves the French one silent, manufacturing the very agreement this
    function exists to withhold.
    """
    parsed = [_parse_one(text, None) for text in locations]
    countries = {country for country, _ in parsed if country}
    if len(countries) != 1:
        return None, None
    agreed = countries.pop()

    # A part that named no country may still name a *place*, and a place the table knows
    # to be shared is a live candidate for somewhere else: "Paris; Geneva" reaches France
    # only by ignoring the Swiss half. Such a part blocks the agreement unless the country
    # the others reached is one of the ones it could mean ("Geneva; Zurich" is Swiss).
    silent = (_candidates(city) for country, city in parsed if not country and city)
    if any(len(could_mean) > 1 and agreed not in could_mean for could_mean in silent):
        return None, None
    return agreed, None


def _parse_one(text: str, hq: str | None) -> tuple[str | None, str | None]:
    """One location. The city table is read last, on whatever city survived the parse, so
    every shape above it — bare token, delimiter part, comma tail — gains it at once."""
    parts = [part for part in (p.strip() for p in _DASH_SEPARATOR.split(text)) if part]
    country, city = _parse_delimited(parts) if len(parts) > 1 else _parse_comma_separated(text)
    if country is None and city is not None:
        country = _country_for_city(city, hq)
    return country, city


def _candidates(city: str) -> tuple[str, ...]:
    """The countries a bare place name could mean — empty when the table has no row."""
    return CITY_TO_COUNTRY.get(city.casefold(), ())


def _country_for_city(city: str, hq: str | None) -> str | None:
    """The country a bare place name states. One candidate is a statement; several is a
    name two countries share, and only the employer's home market can settle it."""
    could_mean = _candidates(city)
    if len(could_mean) == 1:
        return could_mean[0]
    return hq if len(could_mean) > 1 and hq in could_mean else None


def _parse_delimited(parts: list[str]) -> tuple[str | None, str | None]:
    """A ` - ` form pairs a qualifier with a place: "US - San Francisco", "Remote - USA",
    "Hybrid - New York, NY".

    Each part is itself a location, so each is parsed as one — without that recursion
    "Hybrid - New York, NY" loses the US that its comma tail plainly names.

    Position carries meaning here, and it is the opposite of the comma form's: in
    "Chicago, IL" the two-letter tail is Illinois, while in "IL - Tel Aviv" the same token
    is Israel. A part therefore reads a bare code as a *country* code, and a code that
    collides with a US state (CA DE ID IL IN) names nothing on its own.
    """
    parsed = [_parse_comma_separated(part) for part in parts]
    countries = {country for country, _ in parsed if country is not None}
    if len(countries) > 1:
        return None, None
    if countries:
        # The country is settled; a city may sit in the part that named it ("New York, NY")
        # or in one that named no country at all ("US - San Francisco").
        unclaimed = [city for country, city in parsed if country is None and city]
        alongside = [city for country, city in parsed if country is not None and city]
        return countries.pop(), _only(unclaimed) or _only(alongside)

    # Nothing names a country outright — a *spelled-out* US state still does.
    states = [part for part in parts if part.casefold() in US_STATE_NAMES]
    cities = [city for _, city in parsed if city and city.casefold() not in US_STATE_NAMES]
    return ("US" if states else None), _only(cities)


def _only(candidates: list[str]) -> str | None:
    """One candidate is an answer; several is a choice the string did not make."""
    return candidates[0] if len(candidates) == 1 else None


def _parse_comma_separated(cleaned: str) -> tuple[str | None, str | None]:
    segments = [s for s in (seg.strip() for seg in cleaned.split(",")) if s]
    if not segments:
        return None, None
    if len(segments) == 1:
        return _parse_single_segment(segments[0])

    # A comma list can name several countries ("Mexico, Portugal, Spain"). Taking the last
    # one is a coin toss, and the same refusal applies as for the `;` form above.
    named = {code for code in map(_country_code, segments) if code is not None}
    if len(named) > 1:
        return None, None

    first, last = segments[0], segments[-1]
    country = _country_code(last)
    if country is not None:
        city = None if _country_code(first) == country else first
        return country, city
    if _is_us_state(last):
        return "US", first
    code = _iso_code(last)
    if code is not None:
        return code, first
    return None, None


def _parse_single_segment(segment: str) -> tuple[str | None, str | None]:
    country = _country_code(segment) or _iso_code(segment)
    if country is not None:
        return country, None
    if not _is_city(segment):
        return None, None
    return None, segment


def _is_us_state(segment: str) -> bool:
    return (
        segment.replace(".", "").strip().upper() in US_STATE_CODES
        or segment.casefold() in US_STATE_NAMES
    )


def _is_city(segment: str) -> bool:
    """A segment that could name a city: not a region, compass point or placeholder, and
    not a bare code — "IN" is a country or a state, never a town."""
    return (
        segment.casefold() not in NON_CITY_TOKENS
        and len(segment) > 2
        and " or " not in (segment.casefold())
    )


def _iso_code(segment: str) -> str | None:
    code = segment.strip().upper()
    return code if code in _UNAMBIGUOUS_ISO_CODES else None


def _country_code(segment: str) -> str | None:
    key = segment.casefold()
    if key in COUNTRY_NAME_TO_CODE:
        return COUNTRY_NAME_TO_CODE[key]
    # "United States - East" → the part before the dash names the country.
    head = key.split(" - ")[0].strip()
    return COUNTRY_NAME_TO_CODE.get(head)
