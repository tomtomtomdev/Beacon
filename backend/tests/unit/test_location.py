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
