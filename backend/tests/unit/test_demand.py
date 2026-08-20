"""Company-normalized demand ranking (analysis-only, feeds scripts/spot_check_demand.py).

Raw posting counts answer "who posts a lot", not "what is in demand" — one employer with
a large org drowns the signal. These pin the two pure pieces that fix that: collapsing a
title to its role family, and scoring a family with each company's contribution capped.
"""

import pytest

from beacon.domain.demand import DemandRow, RolePosting, normalize_role, rank_roles

ROLE_CASES = [
    ("plain-title-passes-through", "Applied AI Engineer", "applied ai engineer"),
    ("leading-seniority-stripped", "Senior iOS Engineer", "ios engineer"),
    ("abbreviated-seniority-stripped", "Sr. Solutions Architect", "solutions architect"),
    (
        "plus-suffixed-seniority-stripped",
        "Staff+ Site Reliability Engineer",
        "site reliability engineer",
    ),
    ("slashed-seniority-stripped", "Staff/Lead Software Engineer", "software engineer"),
    ("trailing-numeral-stripped", "Software Engineer II", "software engineer"),
    (
        "specialisation-after-comma-dropped",
        "Machine Learning Engineer, Ads Ranking",
        "machine learning engineer",
    ),
    ("parenthetical-dropped", "Senior Software Engineer (iOS)", "software engineer"),
    (
        "location-parenthetical-dropped",
        "Staff Software Engineer (L4) - Back End (Bangkok based)",
        "software engineer",
    ),
    (
        "suffix-after-dash-dropped",
        "Sr. Forward Deployed Engineer (FDE) - Financial Services",
        "forward deployed engineer",
    ),
    ("interior-slash-kept", "Senior Applied ML/AI Scientist", "applied ml/ai scientist"),
    ("hyphenated-word-kept", "Senior Back-End Engineer", "back-end engineer"),
    ("case-and-space-normalised", "  SENIOR   AI  Engineer ", "ai engineer"),
    ("seniority-only-title-is-empty", "Senior", ""),
]


@pytest.mark.parametrize(
    ("title", "expected"),
    [pytest.param(title, expected, id=name) for name, title, expected in ROLE_CASES],
)
def test_normalize_role_collapses_a_title_to_its_role_family(title: str, expected: str) -> None:
    assert normalize_role(title) == expected


def test_rank_roles_counts_postings_and_distinct_firms_per_role() -> None:
    postings = [
        RolePosting("Reddit", "Senior Machine Learning Engineer"),
        RolePosting("Spotify", "Machine Learning Engineer, Ads"),
        RolePosting("Airbnb", "Staff Machine Learning Engineer"),
    ]

    (row,) = rank_roles(postings, cap=3, min_firms=2)

    assert row.role == "machine learning engineer"
    assert row.postings == 3
    assert row.firms == 3


def test_rank_roles_caps_each_firms_contribution_to_the_score() -> None:
    # One employer posting the same role 5 times must not outrank three employers posting
    # it once each — that is the whole point of the normalization.
    concentrated = [RolePosting("Databricks", "Solutions Architect")] * 5
    broad = [
        RolePosting("Stripe", "Applied AI Engineer"),
        RolePosting("Cohere", "Applied AI Engineer"),
        RolePosting("Scale AI", "Applied AI Engineer"),
    ]

    ranked = rank_roles(concentrated + broad, cap=2, min_firms=1)

    assert [row.role for row in ranked] == ["applied ai engineer", "solutions architect"]
    assert ranked[0].score == 3  # three firms, one each
    assert ranked[1].score == 2  # five postings, capped to 2


def test_rank_roles_reports_concentration_so_seed_bias_stays_visible() -> None:
    postings = [
        RolePosting("Databricks", "Forward Deployed Engineer"),
        RolePosting("Databricks", "Sr. Forward Deployed Engineer"),
        RolePosting("Databricks", "Forward Deployed Engineer, Retail"),
        RolePosting("OpenAI", "Forward Deployed Engineer"),
    ]

    (row,) = rank_roles(postings, cap=5, min_firms=2)

    assert row.top_firm == "Databricks"
    assert row.top_firm_share == pytest.approx(0.75)


def test_rank_roles_drops_roles_below_the_firm_threshold() -> None:
    postings = [
        RolePosting("Agoda", "Technical Product Manager"),
        RolePosting("Agoda", "Technical Product Manager, Search"),
        RolePosting("OpenAI", "Applied AI Engineer"),
        RolePosting("Cohere", "Applied AI Engineer"),
    ]

    ranked = rank_roles(postings, cap=3, min_firms=2)

    assert [row.role for row in ranked] == ["applied ai engineer"]


def test_rank_roles_ignores_postings_whose_title_has_no_role_left() -> None:
    ranked = rank_roles(
        [RolePosting("Acme", "Senior"), RolePosting("Beta", "Staff")], cap=3, min_firms=1
    )

    assert ranked == []


def test_rank_roles_breaks_score_ties_deterministically() -> None:
    postings = [
        RolePosting("B Corp", "Data Scientist"),
        RolePosting("A Corp", "Data Scientist"),
        RolePosting("B Corp", "AI Engineer"),
        RolePosting("A Corp", "AI Engineer"),
    ]

    ranked = rank_roles(postings, cap=3, min_firms=2)

    assert [row.role for row in ranked] == ["ai engineer", "data scientist"]
    assert all(isinstance(row, DemandRow) for row in ranked)
