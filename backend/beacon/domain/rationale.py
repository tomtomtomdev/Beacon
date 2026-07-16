"""Deterministic Tier-2 rationale (§11): explain a MatchScore in plain words — no LLM.

Replaces the slice-12e LLM matcher (PROGRESS decision 2026-07-16). build_rationale is pure
wording over the SAME ResumeProfile/JobFacts the score was computed from, so the rationale
can never disagree with the score, never fails, and costs nothing — which is why there is
no cache, no budget, and no port in front of it. Wording is DATA (CLAUDE.md): tune a phrase
or cover a new situation by editing a table/predicate row here plus a parametrized row in
tests/unit/test_rationale.py — never by branching elsewhere.
"""

from beacon.domain.classification import Category, Level
from beacon.domain.resume import JobFacts, MatchRationale, MatchScore, ResumeProfile
from beacon.domain.sponsorship import SponsorTier
from beacon.domain.vocabulary import LEVEL_SENIORITY

# Verdict per overall band, descending — the first floor at or below overall wins.
_VERDICT_BANDS: tuple[tuple[int, str], ...] = (
    (75, "Strong fit — worth applying."),
    (55, "Good fit — worth applying."),
    (35, "Partial fit — worth a look if the gaps are learnable."),
    (0, "Weak fit — probably not worth your time."),
)

# Base sponsorship note per tier; mirrors the _SPONSOR_TIER_FIT semantics in resume.py.
_SPONSOR_NOTES: dict[SponsorTier, str] = {
    SponsorTier.EXPLICIT_YES: "The posting explicitly offers visa sponsorship.",
    SponsorTier.REGISTRY_INFERRED: (
        "No sponsorship language in the posting, but the company appears on a sponsor "
        "registry — a company-level signal, not a per-role guarantee."
    ),
    SponsorTier.UNKNOWN: "No sponsorship signal either way — worth asking early.",
    SponsorTier.EXPLICIT_NO: "The posting rules out visa sponsorship.",
}

# Skill lists in prose are capped so a keyword-stuffed posting can't flood a line.
_MAX_LISTED_SKILLS = 8


def build_rationale(profile: ResumeProfile, job: JobFacts, score: MatchScore) -> MatchRationale:
    """The deterministic deep-match explanation for one scored job. Pure: same inputs, same
    words. score MUST be score_match(profile, job) — the matched/missing sets are read as
    the already-scored facts, never re-derived."""
    return MatchRationale(
        summary=_summary(profile, job, score),
        strengths=_strengths(profile, job, score),
        gaps=_gaps(profile, job, score),
        verdict=_verdict(score.overall),
        sponsor_note=_sponsor_note(profile, job),
    )


def _verdict(overall: int) -> str:
    for floor, verdict in _VERDICT_BANDS:
        if overall >= floor:
            return verdict
    return _VERDICT_BANDS[-1][1]


def _summary(profile: ResumeProfile, job: JobFacts, score: MatchScore) -> str:
    if job.skills:
        coverage = (
            f"Your resume covers {len(score.matched_skills)} of the {len(job.skills)} "
            "skills this posting names"
        )
    else:
        coverage = "This posting names no skills from the shared vocabulary"
    if not job.categories:
        return f"{coverage}."
    if profile.categories & job.categories:
        return f"{coverage}, and the role sits squarely in your field."
    return f"{coverage}, but the role sits outside your usual field."


def _strengths(profile: ResumeProfile, job: JobFacts, score: MatchScore) -> tuple[str, ...]:
    lines: list[str] = []
    if score.matched_skills:
        lines.append(f"Matched skills: {_listed(score.matched_skills)}.")
    shared = profile.categories & job.categories
    if shared:
        lines.append(f"The role's field ({_prose(shared)}) matches your background.")
    gap = _level_gap(profile, job)
    if gap == 0:
        lines.append(f"Seniority is an exact match ({job.level.value}).")
    elif gap == 1:
        lines.append(f"One step up from {profile.level.value} — a reachable stretch.")
    if job.sponsor_tier is SponsorTier.EXPLICIT_YES:
        lines.append("The posting explicitly offers visa sponsorship.")
    elif job.sponsor_tier is SponsorTier.REGISTRY_INFERRED:
        lines.append("The company appears on a sponsor registry.")
    if profile.target_countries and job.country in profile.target_countries:
        lines.append(f"{job.country} is in your relocation strategy.")
    return tuple(lines)


def _gaps(profile: ResumeProfile, job: JobFacts, score: MatchScore) -> tuple[str, ...]:
    lines: list[str] = []
    if score.missing_skills:
        listed = _listed(score.missing_skills)
        lines.append(f"The posting asks for skills your resume doesn't show: {listed}.")
    if job.categories and not (profile.categories & job.categories):
        lines.append(f"The role's field ({_prose(job.categories)}) is outside your profile.")
    gap = _level_gap(profile, job)
    if gap is not None and gap < 0:
        lines.append(
            f"The role reads {-gap} level(s) below your profile "
            f"({job.level.value} vs your {profile.level.value})."
        )
    elif gap is not None and gap >= 2:
        lines.append(f"The role is {gap} seniority steps above your profile.")
    if job.sponsor_tier is SponsorTier.EXPLICIT_NO:
        lines.append("The posting rules out visa sponsorship.")
    elif job.sponsor_tier is SponsorTier.UNKNOWN:
        lines.append("No sponsorship signal in the posting.")
    if profile.target_countries and job.country not in profile.target_countries:
        lines.append(f"{job.country or 'This location'} is outside your target countries.")
    return tuple(lines)


def _sponsor_note(profile: ResumeProfile, job: JobFacts) -> str:
    note = _SPONSOR_NOTES[job.sponsor_tier]
    if not profile.target_countries:
        return note
    if job.country in profile.target_countries:
        return f"{note} {job.country} is in your relocation strategy."
    return f"{note} Note: {job.country or 'this location'} is outside your target countries."


def _level_gap(profile: ResumeProfile, job: JobFacts) -> int | None:
    """Seniority steps from the resume's level up to the job's (negative = job sits below).
    None when either side is UNSPECIFIED — an honest no-signal, so no level line renders."""
    if profile.level is Level.UNSPECIFIED or job.level is Level.UNSPECIFIED:
        return None
    return LEVEL_SENIORITY[job.level] - LEVEL_SENIORITY[profile.level]


def _listed(skills: frozenset[str]) -> str:
    return ", ".join(sorted(skills)[:_MAX_LISTED_SKILLS])


def _prose(categories: frozenset[Category]) -> str:
    return ", ".join(sorted(category.value for category in categories))
