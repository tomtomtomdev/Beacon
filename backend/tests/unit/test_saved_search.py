import pytest

from beacon.domain.saved_search import (
    SearchFilters,
    filters_from_json,
    filters_to_json,
    match_reason,
)


def test_filters_json_roundtrip() -> None:
    filters = SearchFilters(
        q="senior ios",
        countries=("SE", "NL", "IE"),
        categories=("ios",),
        levels=("senior",),
        tiers=("registry_inferred", "explicit_yes"),
    )

    assert filters_from_json(filters_to_json(filters)) == filters


def test_empty_filters_roundtrip() -> None:
    assert filters_from_json(filters_to_json(SearchFilters())) == SearchFilters()


@pytest.mark.parametrize(
    ("filters", "categories", "country", "level", "tier", "expected"),
    [
        pytest.param(
            SearchFilters(
                countries=("SE", "NL", "IE"), categories=("ios",), tiers=("registry_inferred",)
            ),
            ("ios", "backend"),
            "SE",
            "senior",
            "registry_inferred",
            "ios · SE · registry_inferred",
            id="only-the-constrained-dimensions-appear",
        ),
        pytest.param(
            SearchFilters(categories=("ios", "android"), levels=("senior",)),
            ("android",),
            "US",
            "senior",
            "unknown",
            "android · senior",
            id="category-is-the-intersection-with-the-job",
        ),
        pytest.param(
            SearchFilters(tiers=("explicit_yes",)),
            (),
            None,
            None,
            "explicit_yes",
            "explicit_yes",
            id="tier-only-search",
        ),
        pytest.param(
            SearchFilters(),
            ("ios",),
            "SE",
            "senior",
            "unknown",
            "all",
            id="unconstrained-search-matches-all",
        ),
    ],
)
def test_match_reason_names_the_filters_that_fired(
    filters: SearchFilters,
    categories: tuple[str, ...],
    country: str | None,
    level: str | None,
    tier: str,
    expected: str,
) -> None:
    reason = match_reason(filters, categories=categories, country=country, level=level, tier=tier)

    assert reason == expected
