"""Location-string parsing — every case below is a real string from recorded fixtures."""

import pytest

from beacon.domain.countries import CITY_TO_COUNTRY, COUNTRY_NAME_TO_CODE
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
        ("Bangkok", "TH", "Bangkok"),
        ("Kuala Lumpur", "MY", "Kuala Lumpur"),
        ("Bangkok (Central World Office)", "TH", "Bangkok"),
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


def test_delimiter_form_keeps_the_city_when_nothing_names_the_country() -> None:
    """A province is neither a city the table knows nor a country the string names, so
    "Ontario - Remote" yields the place it spells and nothing more."""
    assert parse_location("Ontario - Remote") == (None, "Ontario")


@pytest.mark.parametrize("raw", ["CA", "DE", "ID", "IL", "IN"], ids=lambda v: repr(v))
def test_a_bare_code_that_collides_with_a_us_state_names_nothing(raw: str) -> None:
    """CA/DE/ID/IL/IN read as Canada, Germany, Indonesia, Israel and India — and equally as
    California, Delaware, Idaho, Illinois and Indiana. A guard rather than a corpus row:
    the delimiter strings that used to show this rule ("DE - Berlin") now resolve through
    their city, so without it the collision would go untested."""
    assert parse_location(raw) == (None, None)


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
    [("Georgia", "Georgia"), ("Ontario", "Ontario")],
    ids=lambda v: repr(v),
)
def test_a_bare_token_the_table_does_not_know_still_names_no_country(raw: str, city: str) -> None:
    """A lone token the city table has no row for stays a city and nothing more. "Georgia"
    is the guard: it is a US state *and* a country, so resolving it would have to pick."""
    assert parse_location(raw) == (None, city)


@pytest.mark.parametrize(
    ("raw", "country", "city"),
    [
        # Ranked by the real corpus: these are the bare tokens with jobs behind them.
        ("San Francisco", "US", "San Francisco"),
        ("Amsterdam", "NL", "Amsterdam"),
        ("Bangkok", "TH", "Bangkok"),
        ("東京都中央区", "JP", "東京都中央区"),
        ("Stockholm", "SE", "Stockholm"),
        ("Bengaluru", "IN", "Bengaluru"),
        ("Mexico City", "MX", "Mexico City"),
        ("Copenhagen", "DK", "Copenhagen"),
        ("Oslo", "NO", "Oslo"),
        ("Zurich", "CH", "Zurich"),
        ("Zürich", "CH", "Zürich"),
        ("Lisbon", "PT", "Lisbon"),
        ("Madrid", "ES", "Madrid"),
        ("Seoul", "KR", "Seoul"),
        # The table reads wherever a city survives the parse, so the delimiter form
        # that 17a could only half-read now resolves its country too.
        ("DE - Berlin", "DE", "Berlin"),
        ("IN - Bangalore", "IN", "Bangalore"),
        ("Hybrid - San Francisco", "US", "San Francisco"),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_unambiguous_city_resolves_to_its_country(raw: str, country: str, city: str) -> None:
    """A city that names exactly one country is as plain a statement as the country name."""
    assert parse_location(raw) == (country, city)


@pytest.mark.parametrize(
    "raw",
    [
        "Athens",  # Georgia
        "Birmingham",  # Alabama
        "Cambridge",  # Massachusetts
        "Geneva",  # Illinois
        "Manchester",  # New Hampshire
        "Melbourne",  # Florida
        "San Jose",  # Costa Rica
        "Vancouver",  # Washington
    ],
    ids=lambda v: repr(v),
)
def test_a_city_shared_with_another_country_does_not_resolve_alone(raw: str) -> None:
    """The trap this table exists to survive: each of these names a place in two countries,
    so the bare string states no country — only the city it spells."""
    assert parse_location(raw) == (None, raw)


@pytest.mark.parametrize(
    ("raw", "hq", "country"),
    [
        # Proton is Swiss, so its Geneva req is the Swiss one; its London, Barcelona and
        # Vilnius reqs are not thereby Swiss.
        ("Geneva", "CH", "CH"),
        ("London", "CH", "GB"),
        ("Barcelona", "CH", "ES"),
        ("Vilnius", "CH", "LT"),
        # The tie-break only chooses between candidates the table already names. An
        # employer's home market never supplies a country for a place it does not know.
        ("Bengaluru", "CH", "IN"),
        ("Ontario", "CH", None),
        ("Remote", "CH", None),
        ("Cambridge", "GB", "GB"),
        ("San Jose", "CR", "CR"),
        # No home market on offer, or one that is not a candidate, changes nothing.
        ("Geneva", None, None),
        ("Geneva", "", None),
        ("Geneva", "DE", None),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_an_ambiguous_city_is_resolved_by_the_employer_hq(
    raw: str, hq: str | None, country: str | None
) -> None:
    assert parse_location(raw, hq)[0] == country


def test_city_table_has_no_row_the_country_table_lacks() -> None:
    """A typo'd country code fails here, at import, rather than at the first Jakarta job."""
    known = set(COUNTRY_NAME_TO_CODE.values())
    unknown = {
        code for candidates in CITY_TO_COUNTRY.values() for code in candidates if code not in known
    }

    assert unknown == set()


@pytest.mark.parametrize(
    ("raw", "country"),
    [
        # Proton is Swiss and advertises these two cities together. Letting its home market
        # settle "Geneva" while "Paris" stays unresolved manufactures the agreement that
        # `_parse_many` exists to withhold — the ad names two countries, not one.
        ("Paris; Geneva", None),
        ("Geneva; Paris", None),
        ("London; Geneva", None),
        ("London; Paris; Geneva", None),
        # Agreement the string itself reaches is untouched: both of these are Swiss.
        ("Geneva; Zurich", "CH"),
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_the_employer_hq_never_settles_a_multi_location_string(
    raw: str, country: str | None
) -> None:
    """A home market can settle which country a shared *name* means. It cannot choose
    between two locations a posting lists side by side."""
    assert parse_location(raw, "CH") == (country, None)


@pytest.mark.parametrize(
    ("raw", "country"),
    [
        ("Toronto", "CA"),  # Toronto, Ohio — pop. 5,000
        ("London", "GB"),  # London, Ontario — real, but not what a tech ad means
        ("Paris", "FR"),  # Paris, Texas — pop. 25,000
    ],
    ids=lambda v: repr(v) if isinstance(v, str) else str(v),
)
def test_a_name_shared_only_with_a_place_nobody_hires_in_resolves(raw: str, country: str) -> None:
    """A row is ambiguous when *both* referents plausibly host jobs, not merely when the
    name occurs twice on a map. Measured over the corpus, treating these three as shared
    let the employer's home market answer for them and got 27 of 81 rows wrong — every one
    a multinational advertising outside its home country, which an HQ cannot detect."""
    assert parse_location(raw) == (country, raw)
