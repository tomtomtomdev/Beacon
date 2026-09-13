"""Location-string parsing — every case below is a real string from recorded fixtures."""

import pytest

from beacon.domain.location import parse_location


@pytest.mark.parametrize(
    ("raw", "country", "city"),
    [
        ("Bangkok, Thailand", "TH", "Bangkok"),
        ("Tokyo, Japan", "JP", "Tokyo"),
        ("Amsterdam, North Holland, Netherlands", "NL", "Amsterdam"),
        ("Düsseldorf, North Rhine-Westphalia, Germany", "DE", "Düsseldorf"),
        ("Sydney, New South Wales, Australia", "AU", "Sydney"),
        ("Dublin, Ireland (Hybrid)", "IE", "Dublin"),
        ("United States (Remote)", "US", None),
        ("United States - East (Remote)", "US", None),
        ("Ireland (Remote)", "IE", None),
        ("Singapore", "SG", None),
        ("Boston, MA", "US", "Boston"),
        ("Chicago, IL", "US", "Chicago"),
        ("Bangkok", None, "Bangkok"),
        ("Kuala Lumpur", None, "Kuala Lumpur"),
        ("Bangkok (Central World Office)", None, "Bangkok"),
        ("Bangkok or Shanghai", None, None),
        ("North America (Remote)", None, None),
        ("", None, None),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_parse_location(raw: str, country: str | None, city: str | None) -> None:
    assert parse_location(raw) == (country, city)


@pytest.mark.parametrize(
    ("raw", "country", "city"),
    [
        ("Austin, Texas", "US", "Austin"),
        ("Bellevue, Washington", "US", "Bellevue"),
        ("Chicago, Illinois", "US", "Chicago"),
        ("San Francisco, California", "US", "San Francisco"),
        ("Mountain View, California", "US", "Mountain View"),
        ("Washington, D.C.", "US", "Washington"),
        ("Atlanta, Georgia", "US", "Atlanta"),
        # A comma tail is a US state first — "IL" is Illinois, never Israel — and only then
        # a country code that cannot be one.
        ("Stockholm, SE", "SE", "Stockholm"),
        ("Chicago, IL", "US", "Chicago"),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_us_state_name_resolves_like_its_code(raw: str, country: str, city: str) -> None:
    """`US_STATE_CODES` held two-letter codes only, so a spelled-out state fell through and
    the function returned (None, None) — losing the city as well as the country."""
    assert parse_location(raw) == (country, city)


@pytest.mark.parametrize(
    ("raw", "country", "city"),
    [
        ("SG - Singapore", "SG", None),
        ("Remote - USA", "US", None),
        ("Remote - United States", "US", None),
        ("US - Remote", "US", None),
        ("US - San Francisco", "US", "San Francisco"),
        ("US - New York", "US", "New York"),
        ("AU - Sydney", "AU", "Sydney"),
        ("NL - Amsterdam", "NL", "Amsterdam"),
        ("MY - Kuala Lumpur", "MY", "Kuala Lumpur"),
        ("Remote - India", "IN", None),
        ("Remote - California", "US", None),
        ("Northeast - United States", "US", None),
        # Each part is a location in its own right — found by re-parsing the real corpus,
        # where these three had silently stopped resolving.
        ("Hybrid - New York, NY", "US", "New York"),
        ("Remote - USA, United States of America", "US", None),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_delimiter_form_reads_the_country_part(raw: str, country: str, city: str | None) -> None:
    """A ` - ` form names its country outright; reading it invents nothing."""
    assert parse_location(raw) == (country, city)


@pytest.mark.parametrize(
    ("raw", "city"),
    [
        ("Hybrid - San Francisco", "San Francisco"),
        ("IN - Bangalore", "Bangalore"),
        ("DE - Berlin", "Berlin"),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_delimiter_form_without_a_country_still_yields_the_city(raw: str, city: str) -> None:
    """`IN`/`DE` are Indiana and Delaware as readily as India and Germany, so a bare
    two-letter code that collides with a US state resolves no country here — but the city
    is still worth keeping, and is what a city table can later resolve against."""
    assert parse_location(raw) == (None, city)


@pytest.mark.parametrize(
    ("raw", "country"),
    [
        ("Berlin, Germany; Munich, Germany", "DE"),
        ("Toronto, Canada; Canada", "CA"),
        ("San Francisco, CA • New York, NY • United States", "US"),
        ("Mountain View, California; San Francisco, California", "US"),
        ("Maryland; Virginia; Washington, D.C.", "US"),
        ("Central - United States; Northeast - United States", "US"),
        # Two countries, one country column: naming either would be a coin toss.
        ("San Francisco, CA; Toronto, Canada; Seattle, WA", None),
        ("Dublin, Ireland; London, England", None),
        # A comma list names countries just as plainly as a semicolon one does; the old
        # code took whichever came last, which silently made a five-country ad Vietnamese.
        ("Canada, United States", None),
        ("Mexico, Portugal, Spain", None),
        ("Australia, Hong Kong, Taiwan, Thailand, Vietnam", None),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_multi_location_resolves_only_when_the_parts_agree(raw: str, country: str | None) -> None:
    assert parse_location(raw) == (country, None)


@pytest.mark.parametrize(
    "raw",
    [
        "Anywhere in the World",
        "N/A",
        "Remote",
        "EMEA",
        "AMER",
        "Worldwide",
    ],
    ids=lambda v: repr(v),
)
def test_still_refuses_to_guess(raw: str) -> None:
    """These are correct today and must stay correct: a string that names no place yields
    no country *and* no city — "Anywhere in the World" is not a city."""
    assert parse_location(raw) == (None, None)


@pytest.mark.parametrize(
    ("raw", "city"),
    [("Bangkok", "Bangkok"), ("Georgia", "Georgia"), ("Kuala Lumpur", "Kuala Lumpur")],
    ids=lambda v: repr(v),
)
def test_a_bare_token_still_names_no_country(raw: str, city: str) -> None:
    """A lone token stays a city. "Georgia" is the guard: it is a US state *and* a country,
    so resolving bare state names would have to pick one — 17b's table decides, not this."""
    assert parse_location(raw) == (None, city)
