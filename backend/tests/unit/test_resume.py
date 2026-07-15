"""Resume fit scoring domain (§11): build_profile + score_match — pure, deterministic.

The highest-value tests in the slice: this is the correctness surface. score_match is a
soft, explainable signal (never a filter-out), so the tests pin *relationships* (aligned >
disjoint, stretch-up mild, over-qualified penalised, on-strategy sponsor wins) plus the
exact matched/missing skill sets and determinism.
"""

from beacon.domain.classification import Category, Level
from beacon.domain.resume import (
    JobFacts,
    MatchScore,
    ResumeProfile,
    build_profile,
    score_match,
)
from beacon.domain.sponsorship import SponsorTier


def _profile(
    *,
    skills: set[str],
    categories: set[Category],
    level: Level,
    target_countries: set[str] | None = None,
) -> ResumeProfile:
    return ResumeProfile(
        skills=frozenset(skills),
        categories=frozenset(categories),
        level=level,
        years=None,
        target_countries=frozenset(target_countries or set()),
    )


def _job(
    *,
    skills: set[str],
    categories: set[Category],
    level: Level,
    country: str | None = "NL",
    tier: SponsorTier = SponsorTier.UNKNOWN,
) -> JobFacts:
    return JobFacts(
        skills=frozenset(skills),
        categories=frozenset(categories),
        level=level,
        country=country,
        sponsor_tier=tier,
    )


# --- build_profile ---------------------------------------------------------------------


def test_build_profile_extracts_skills_category_level_years() -> None:
    profile = build_profile("Senior iOS Engineer — 8 years of Swift, SwiftUI and UIKit")

    assert profile.categories == frozenset({Category.IOS})
    assert profile.level == Level.SENIOR
    assert profile.years == 8
    assert {"swift", "swiftui", "uikit"} <= profile.skills


def test_build_profile_records_target_countries() -> None:
    profile = build_profile(
        "Backend engineer, Django and Postgres", target_countries=frozenset({"NL"})
    )

    assert Category.BACKEND in profile.categories
    assert profile.target_countries == frozenset({"NL"})


# --- score_match: skills + category + level components ----------------------------------


def test_score_match_full_alignment_scores_high() -> None:
    profile = _profile(
        skills={"swift", "swiftui", "uikit"}, categories={Category.IOS}, level=Level.SENIOR
    )
    job = _job(
        skills={"swift", "swiftui"},
        categories={Category.IOS},
        level=Level.SENIOR,
        tier=SponsorTier.EXPLICIT_YES,
    )

    score = score_match(profile, job)

    assert score.overall >= 90
    assert score.skills_score == 100  # the resume covers every skill the job asks for


def test_score_match_disjoint_skills_and_category_scores_low() -> None:
    profile = _profile(skills={"swift", "swiftui"}, categories={Category.IOS}, level=Level.SENIOR)
    job = _job(
        skills={"react", "css"},
        categories={Category.FRONTEND},
        level=Level.SENIOR,
        tier=SponsorTier.UNKNOWN,
    )

    score = score_match(profile, job)

    assert score.overall <= 40
    assert score.skills_score == 0


def test_level_penalises_overqualification_more_than_a_stretch_up() -> None:
    profile = _profile(skills=set(), categories=set(), level=Level.SENIOR)
    exact = score_match(profile, _job(skills=set(), categories=set(), level=Level.SENIOR))
    stretch = score_match(profile, _job(skills=set(), categories=set(), level=Level.STAFF))
    overqualified = score_match(profile, _job(skills=set(), categories=set(), level=Level.JUNIOR))

    assert exact.level_score == 100
    assert 0 < stretch.level_score < exact.level_score  # staff is a mild stretch, not a wall
    assert 0 < overqualified.level_score < stretch.level_score  # junior fits worse


# --- score_match: sponsorship / country fit (Beacon's differentiator) -------------------


def test_sponsor_score_rewards_target_country_and_positive_tier() -> None:
    profile = _profile(
        skills=set(), categories=set(), level=Level.SENIOR, target_countries={"NL", "SE"}
    )

    def sponsor(country: str | None, tier: SponsorTier) -> int:
        job = _job(skills=set(), categories=set(), level=Level.SENIOR, country=country, tier=tier)
        return score_match(profile, job).sponsor_score

    on_strategy_yes = sponsor("NL", SponsorTier.EXPLICIT_YES)
    on_strategy_registry = sponsor("SE", SponsorTier.REGISTRY_INFERRED)
    off_strategy_yes = sponsor("US", SponsorTier.EXPLICIT_YES)
    on_strategy_no = sponsor("NL", SponsorTier.EXPLICIT_NO)

    assert on_strategy_yes > on_strategy_no
    assert on_strategy_yes > off_strategy_yes
    assert on_strategy_registry > off_strategy_yes


# --- explainability + purity ------------------------------------------------------------


def test_score_reports_matched_and_missing_skills() -> None:
    profile = _profile(
        skills={"swift", "swiftui", "kotlin"}, categories={Category.IOS}, level=Level.SENIOR
    )
    job = _job(skills={"swift", "swiftui", "uikit"}, categories={Category.IOS}, level=Level.SENIOR)

    score = score_match(profile, job)

    assert score.matched_skills == frozenset({"swift", "swiftui"})
    assert score.missing_skills == frozenset({"uikit"})  # job asks, resume lacks


def test_score_match_is_deterministic() -> None:
    profile = _profile(skills={"swift"}, categories={Category.IOS}, level=Level.SENIOR)
    job = _job(
        skills={"swift", "uikit"},
        categories={Category.IOS},
        level=Level.SENIOR,
        tier=SponsorTier.REGISTRY_INFERRED,
    )

    first = score_match(profile, job)
    second = score_match(profile, job)

    assert first == second
    assert isinstance(first, MatchScore)
    assert 0 <= first.overall <= 100
