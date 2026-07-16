"""Deterministic Tier-2 rationale (§11): build_rationale — pure wording over scored facts.

Table-driven like the vocabulary tests: a misworded, missing, or misfiring line found in
use becomes a new parametrized row here — never a branch anywhere else. The generator
explains exactly the facts score_match scored (same ResumeProfile/JobFacts), so every test
builds its MatchScore through score_match unless it is pinning a verdict band boundary.
"""

import pytest

from beacon.domain.classification import Category, Level
from beacon.domain.rationale import build_rationale
from beacon.domain.resume import JobFacts, MatchRationale, MatchScore, ResumeProfile, score_match
from beacon.domain.sponsorship import SponsorTier


def _profile(
    *,
    skills: set[str] | None = None,
    categories: set[Category] | None = None,
    level: Level = Level.UNSPECIFIED,
    target_countries: set[str] | None = None,
) -> ResumeProfile:
    return ResumeProfile(
        skills=frozenset(skills or set()),
        categories=frozenset(categories or set()),
        level=level,
        years=None,
        target_countries=frozenset(target_countries or set()),
    )


def _job(
    *,
    skills: set[str] | None = None,
    categories: set[Category] | None = None,
    level: Level = Level.UNSPECIFIED,
    country: str | None = None,
    tier: SponsorTier = SponsorTier.UNKNOWN,
) -> JobFacts:
    return JobFacts(
        skills=frozenset(skills or set()),
        categories=frozenset(categories or set()),
        level=level,
        country=country,
        sponsor_tier=tier,
    )


def _rationale(profile: ResumeProfile, job: JobFacts) -> MatchRationale:
    return build_rationale(profile, job, score_match(profile, job))


def _score(overall: int) -> MatchScore:
    return MatchScore(
        overall=overall,
        skills_score=0,
        level_score=0,
        sponsor_score=0,
        matched_skills=frozenset(),
        missing_skills=frozenset(),
    )


# --- verdict: overall band table ---------------------------------------------------------

STRONG = "Strong fit — worth applying."
GOOD = "Good fit — worth applying."
PARTIAL = "Partial fit — worth a look if the gaps are learnable."
WEAK = "Weak fit — probably not worth your time."


@pytest.mark.parametrize(
    ("overall", "verdict"),
    [
        (100, STRONG),
        (75, STRONG),
        (74, GOOD),
        (55, GOOD),
        (54, PARTIAL),
        (35, PARTIAL),
        (34, WEAK),
        (0, WEAK),
    ],
    ids=["100", "75-band-edge", "74", "55-band-edge", "54", "35-band-edge", "34", "0"],
)
def test_verdict_tracks_the_overall_band(overall: int, verdict: str) -> None:
    rationale = build_rationale(_profile(), _job(), _score(overall))

    assert rationale.verdict == verdict


# --- summary: skill-coverage clause + category clause ------------------------------------


def test_summary_counts_covered_skills_and_confirms_the_field() -> None:
    profile = _profile(skills={"swift", "swiftui"}, categories={Category.IOS})
    job = _job(skills={"swift", "swiftui", "uikit"}, categories={Category.IOS})

    rationale = _rationale(profile, job)

    assert rationale.summary == (
        "Your resume covers 2 of the 3 skills this posting names, "
        "and the role sits squarely in your field."
    )


def test_summary_flags_a_field_mismatch() -> None:
    profile = _profile(skills={"swift"}, categories={Category.IOS})
    job = _job(skills={"react", "swift"}, categories={Category.FRONTEND})

    rationale = _rationale(profile, job)

    assert rationale.summary == (
        "Your resume covers 1 of the 2 skills this posting names, "
        "but the role sits outside your usual field."
    )


def test_summary_is_honest_when_the_posting_names_no_vocabulary_skills() -> None:
    rationale = _rationale(_profile(skills={"swift"}), _job(skills=set()))

    assert rationale.summary == "This posting names no skills from the shared vocabulary."


# --- strengths: ordered predicate rows ----------------------------------------------------


@pytest.mark.parametrize(
    ("profile", "job", "line"),
    [
        (
            _profile(skills={"swiftui", "swift"}),
            _job(skills={"swift", "swiftui", "uikit"}),
            "Matched skills: swift, swiftui.",
        ),
        (
            _profile(categories={Category.IOS, Category.BACKEND}),
            _job(categories={Category.IOS}),
            "The role's field (ios) matches your background.",
        ),
        (
            _profile(level=Level.SENIOR),
            _job(level=Level.SENIOR),
            "Seniority is an exact match (senior).",
        ),
        (
            # One rung on LEVEL_SENIORITY's ladder (senior=2 -> lead=3); senior->staff is 2.
            _profile(level=Level.SENIOR),
            _job(level=Level.LEAD),
            "One step up from senior — a reachable stretch.",
        ),
        (
            _profile(),
            _job(tier=SponsorTier.EXPLICIT_YES),
            "The posting explicitly offers visa sponsorship.",
        ),
        (
            _profile(),
            _job(tier=SponsorTier.REGISTRY_INFERRED),
            "The company appears on a sponsor registry.",
        ),
        (
            _profile(target_countries={"NL", "SE"}),
            _job(country="NL"),
            "NL is in your relocation strategy.",
        ),
    ],
    ids=[
        "matched-skills-sorted",
        "category-overlap",
        "exact-level",
        "one-step-stretch",
        "explicit-yes",
        "registry-inferred",
        "target-country-hit",
    ],
)
def test_strengths_rows_fire_on_their_predicate(
    profile: ResumeProfile, job: JobFacts, line: str
) -> None:
    assert line in _rationale(profile, job).strengths


def test_matched_skills_line_is_first_and_capped_at_eight() -> None:
    many = {f"skill-{i}" for i in range(10)}
    profile = _profile(skills=many)
    job = _job(skills=many)

    rationale = _rationale(profile, job)

    expected = ", ".join(sorted(many)[:8])
    assert rationale.strengths[0] == f"Matched skills: {expected}."


# --- gaps: ordered predicate rows ---------------------------------------------------------


@pytest.mark.parametrize(
    ("profile", "job", "line"),
    [
        (
            _profile(skills={"swift"}),
            _job(skills={"swift", "uikit", "coredata"}),
            "The posting asks for skills your resume doesn't show: coredata, uikit.",
        ),
        (
            _profile(categories={Category.IOS}),
            _job(categories={Category.FRONTEND}),
            "The role's field (frontend) is outside your profile.",
        ),
        (
            _profile(level=Level.SENIOR),
            _job(level=Level.JUNIOR),
            "The role reads 1 level(s) below your profile (junior vs your senior).",
        ),
        (
            _profile(level=Level.JUNIOR),
            _job(level=Level.LEAD),
            "The role is 2 seniority steps above your profile.",
        ),
        (
            _profile(),
            _job(tier=SponsorTier.EXPLICIT_NO),
            "The posting rules out visa sponsorship.",
        ),
        (
            _profile(),
            _job(tier=SponsorTier.UNKNOWN),
            "No sponsorship signal in the posting.",
        ),
        (
            _profile(target_countries={"NL"}),
            _job(country="US"),
            "US is outside your target countries.",
        ),
        (
            _profile(target_countries={"NL"}),
            _job(country=None),
            "This location is outside your target countries.",
        ),
    ],
    ids=[
        "missing-skills-sorted",
        "category-miss",
        "overqualified",
        "two-step-stretch",
        "explicit-no",
        "unknown-tier",
        "off-strategy-country",
        "off-strategy-no-country",
    ],
)
def test_gaps_rows_fire_on_their_predicate(
    profile: ResumeProfile, job: JobFacts, line: str
) -> None:
    assert line in _rationale(profile, job).gaps


def test_level_rows_are_skipped_when_either_side_is_unspecified() -> None:
    unspecified_profile = _rationale(_profile(), _job(level=Level.SENIOR))
    unspecified_job = _rationale(_profile(level=Level.SENIOR), _job())

    for rationale in (unspecified_profile, unspecified_job):
        assert not any("Seniority" in line or "step" in line for line in rationale.strengths)
        assert not any("level" in line or "step" in line for line in rationale.gaps)


# --- sponsor_note: tier table + relocation-strategy suffix --------------------------------

YES_NOTE = "The posting explicitly offers visa sponsorship."
REGISTRY_NOTE = (
    "No sponsorship language in the posting, but the company appears on a sponsor "
    "registry — a company-level signal, not a per-role guarantee."
)
UNKNOWN_NOTE = "No sponsorship signal either way — worth asking early."
NO_NOTE = "The posting rules out visa sponsorship."


@pytest.mark.parametrize(
    ("tier", "note"),
    [
        (SponsorTier.EXPLICIT_YES, YES_NOTE),
        (SponsorTier.REGISTRY_INFERRED, REGISTRY_NOTE),
        (SponsorTier.UNKNOWN, UNKNOWN_NOTE),
        (SponsorTier.EXPLICIT_NO, NO_NOTE),
    ],
    ids=["explicit-yes", "registry", "unknown", "explicit-no"],
)
def test_sponsor_note_without_a_relocation_strategy_is_the_bare_tier_note(
    tier: SponsorTier, note: str
) -> None:
    rationale = _rationale(_profile(), _job(tier=tier, country="NL"))

    assert rationale.sponsor_note == note


@pytest.mark.parametrize(
    ("country", "suffix"),
    [
        ("NL", " NL is in your relocation strategy."),
        ("US", " Note: US is outside your target countries."),
        (None, " Note: this location is outside your target countries."),
    ],
    ids=["on-strategy", "off-strategy", "no-country"],
)
def test_sponsor_note_appends_the_relocation_strategy_fit(country: str | None, suffix: str) -> None:
    profile = _profile(target_countries={"NL", "SE"})

    rationale = _rationale(profile, _job(tier=SponsorTier.EXPLICIT_YES, country=country))

    assert rationale.sponsor_note == YES_NOTE + suffix


# --- purity -------------------------------------------------------------------------------


def test_build_rationale_is_deterministic_over_multi_element_sets() -> None:
    profile = _profile(
        skills={"swift", "swiftui", "kotlin", "react"},
        categories={Category.IOS, Category.ANDROID},
        level=Level.SENIOR,
        target_countries={"NL", "SE", "DE"},
    )
    job = _job(
        skills={"swift", "uikit", "coredata", "react", "css"},
        categories={Category.IOS, Category.FRONTEND},
        level=Level.STAFF,
        country="DE",
        tier=SponsorTier.REGISTRY_INFERRED,
    )

    first = _rationale(profile, job)
    second = _rationale(profile, job)

    assert first == second
