from beacon.domain.dedup import (
    HAMMING_THRESHOLD,
    DedupRow,
    assign_canonicals,
    hamming,
    normalize_title,
    simhash,
)

BASE = (
    "We are hiring a senior backend engineer to build scalable distributed systems in "
    "Python and Go. You will own services end to end, mentor peers, and shape our platform "
    "architecture. Remote friendly across Europe with strong async collaboration."
)


def test_simhash_is_deterministic() -> None:
    assert simhash(BASE) == simhash(BASE)


def test_simhash_near_duplicate_within_threshold() -> None:
    # Same posting a second source re-listed with a boilerplate footer + whitespace churn.
    variant = BASE.replace("Python and Go", "Python  and   Go") + " Apply now on our careers page."

    assert hamming(simhash(BASE), simhash(variant)) <= HAMMING_THRESHOLD


def test_simhash_different_role_exceeds_threshold() -> None:
    other = (
        "Seeking a brand marketing manager to lead consumer campaigns, social media strategy, "
        "and creative partnerships for our lifestyle products across retail channels."
    )

    assert hamming(simhash(BASE), simhash(other)) > HAMMING_THRESHOLD


def test_normalize_title_collapses_case_and_whitespace() -> None:
    assert normalize_title("  Senior  iOS   Engineer ") == normalize_title("senior ios engineer")


def test_normalize_title_keeps_distinct_roles_distinct() -> None:
    assert normalize_title("Senior iOS Engineer") != normalize_title("Senior Android Engineer")


def _row(
    job_id: int, title: str, description: str, *, company_id: int = 1, country: str | None = "IE"
) -> DedupRow:
    return DedupRow(
        id=job_id, company_id=company_id, title=title, country=country, description=description
    )


def test_singletons_map_to_themselves() -> None:
    rows = [_row(1, "Backend Engineer", BASE), _row(2, "Frontend Engineer", BASE)]

    assert assign_canonicals(rows) == {1: 1, 2: 2}


def test_canonicalization_links_duplicate_to_lowest_id() -> None:
    variant = BASE + " Apply now on our careers page."
    rows = [_row(5, "Backend Engineer", BASE), _row(9, "Backend Engineer", variant)]

    # The later-inserted duplicate (id 9) adopts the earliest row (id 5) as canonical.
    assert assign_canonicals(rows) == {5: 5, 9: 5}


def test_three_sources_collapse_to_one_canonical() -> None:
    rows = [
        _row(30, "Backend Engineer", BASE),
        _row(10, "Backend Engineer", BASE + " footer a"),
        _row(20, "Backend Engineer", BASE + " footer b"),
    ]

    assert assign_canonicals(rows) == {10: 10, 20: 10, 30: 10}


def test_no_false_merge_on_different_titles() -> None:
    # Same company, same country, byte-identical description — but genuinely different roles.
    rows = [_row(1, "Senior iOS Engineer", BASE), _row(2, "Senior Android Engineer", BASE)]

    assert assign_canonicals(rows) == {1: 1, 2: 2}


def test_no_merge_when_descriptions_diverge() -> None:
    # A generic title collision at one company: same title+country, unrelated postings.
    other = (
        "Seeking a brand marketing manager to lead consumer campaigns, social media strategy, "
        "and creative partnerships for our lifestyle products across retail channels."
    )
    rows = [_row(1, "Software Engineer", BASE), _row(2, "Software Engineer", other)]

    assert assign_canonicals(rows) == {1: 1, 2: 2}


def test_no_merge_across_companies_or_countries() -> None:
    rows = [
        _row(1, "Backend Engineer", BASE, company_id=1, country="IE"),
        _row(2, "Backend Engineer", BASE, company_id=2, country="IE"),  # different company
        _row(3, "Backend Engineer", BASE, company_id=1, country="US"),  # different country
    ]

    assert assign_canonicals(rows) == {1: 1, 2: 2, 3: 3}
