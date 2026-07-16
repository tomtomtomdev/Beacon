"""Resume fit scoring (§11) — pure domain, no IO, no API cost.

Tier 1 of the two-tier match design: a deterministic, explainable score over the SAME
vocabulary the job classifier uses (domain/vocabulary.py), so a resume's category/level/
skills are computed the way a job's are and the two are directly comparable. Being pure and
cheap is the whole point — this ranks the entire DB for free; the LLM tier (§11 Tier 2, a
separate adapter) only ever upgrades one job at a time.

Fit is a soft signal exactly like sponsorship: an opt-in sort key, never a filter-out. The
weights below shape the ranking; they are the one place to tune it.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

from beacon.domain.classification import Category, Level
from beacon.domain.sponsorship import SponsorTier
from beacon.domain.vocabulary import (
    LEVEL_SENIORITY,
    extract_categories,
    extract_skills,
    resolve_level,
    years_of_experience,
)


@dataclass(frozen=True, slots=True)
class ResumeProfile:
    """A resume reduced to the same structured facts a job carries, so they compare. Built
    once per resume by build_profile and cached (resume_hash) by the ingest use case."""

    skills: frozenset[str]
    categories: frozenset[Category]
    level: Level
    years: int | None
    # Optional relocation strategy from a small form; empty means country-agnostic scoring.
    target_countries: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class Resume:
    """An uploaded resume: its raw text, the extracted profile, and its content hash. The
    ingest use case keeps exactly one active at a time. id/created_at are None only for an
    unsaved instance; a persisted Resume always has both."""

    id: int | None
    label: str
    source_text: str
    profile: ResumeProfile
    resume_hash: str
    active: bool
    created_at: datetime | None


def resume_hash(source_text: str) -> str:
    """Content address for a resume (SPEC §11): sha256 of the raw pasted/uploaded text, so
    re-uploading identical text dedupes to the same row and reuses its cached scores."""
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def profile_to_json(profile: ResumeProfile) -> str:
    """Serialize a profile for the resumes.profile_json column. Sets → sorted lists so the
    JSON is stable and diffs cleanly."""
    return json.dumps(
        {
            "skills": sorted(profile.skills),
            "categories": sorted(category.value for category in profile.categories),
            "level": profile.level.value,
            "years": profile.years,
            "target_countries": sorted(profile.target_countries),
        }
    )


def profile_from_json(raw: str) -> ResumeProfile:
    data = json.loads(raw)
    return ResumeProfile(
        skills=frozenset(data["skills"]),
        categories=frozenset(Category(value) for value in data["categories"]),
        level=Level(data["level"]),
        years=data["years"],
        target_countries=frozenset(data["target_countries"]),
    )


@dataclass(frozen=True, slots=True)
class JobFacts:
    """The read-side facts score_match compares a resume against, assembled by the
    application layer from a canonical job (its text -> skills, its classification, country,
    resolved sponsor tier). Kept distinct from NormalizedJob so scoring stays pure and free
    of the ingest/persistence shapes."""

    skills: frozenset[str]
    categories: frozenset[Category]
    level: Level
    country: str | None
    sponsor_tier: SponsorTier


@dataclass(frozen=True, slots=True)
class MatchScore:
    """Overall 0–100 plus the sub-scores the drawer's Fit card shows and the cache persists
    (skills/level/sponsor — SPEC §7). Category alignment folds into overall (no stored column
    of its own). matched/missing name which skills hit and which the job wants but the resume
    lacks, so the score is explainable, not a black box."""

    overall: int
    skills_score: int
    level_score: int
    sponsor_score: int
    matched_skills: frozenset[str]
    missing_skills: frozenset[str]


@dataclass(frozen=True, slots=True)
class MatchRationale:
    """The Tier-2 LLM deep-match output (§11): a fit summary, concrete strengths, gaps to close,
    a one-line 'worth applying?' verdict, and a sponsorship-fit note. Stored as JSON in
    job_match_scores.llm_rationale and shown under the drawer's Fit card. The LLM is an upgrader:
    this is null until the user asks for it, and any LLM failure leaves the heuristic score alone."""

    summary: str
    strengths: tuple[str, ...]
    gaps: tuple[str, ...]
    verdict: str
    sponsor_note: str


@dataclass(frozen=True, slots=True)
class DeepMatchJob:
    """The single-job context the Matcher port hands the LLM: the posting's own text (title +
    description) plus the country/sponsor tier and the heuristic score, so the rationale can
    speak to the matched/missing skills and Beacon's sponsorship signal. Assembled by the
    deep-match use case from a canonical job — never the whole DB (Tier 2 is one job at a time)."""

    title: str
    description: str
    country: str | None
    sponsor_tier: SponsorTier
    heuristic: MatchScore


def rationale_to_json(rationale: MatchRationale) -> str:
    """Serialize a rationale for the llm_rationale column — a readable JSON object, not a pickle,
    so the stored value can be inspected and a later migration can read it."""
    return json.dumps(
        {
            "summary": rationale.summary,
            "strengths": list(rationale.strengths),
            "gaps": list(rationale.gaps),
            "verdict": rationale.verdict,
            "sponsor_note": rationale.sponsor_note,
        }
    )


def rationale_from_json(raw: str) -> MatchRationale:
    data = json.loads(raw)
    return MatchRationale(
        summary=data["summary"],
        strengths=tuple(data["strengths"]),
        gaps=tuple(data["gaps"]),
        verdict=data["verdict"],
        sponsor_note=data["sponsor_note"],
    )


# Sub-score weights (sum to 1.0). Skills dominate; sponsorship/country is Beacon's edge over
# a generic matcher but is the smallest slice — it nudges, it doesn't decide.
SKILL_WEIGHT = 0.40
CATEGORY_WEIGHT = 0.25
LEVEL_WEIGHT = 0.20
SPONSOR_WEIGHT = 0.15

# Level-fit penalties per seniority step. Over-qualification (job below the resume) is
# penalised harder than a stretch up (job above): a senior won't take a junior role, but
# stretching toward staff is a mild, not-zero, reach.
LEVEL_STRETCH_PENALTY = 0.12
LEVEL_OVERQUALIFIED_PENALTY = 0.30
# Neither side names a level → a weak, neutral signal rather than a reward or a penalty.
LEVEL_UNKNOWN_FIT = 0.70

# Sponsor tier → base fit (a target-country job with a positive tier is the ideal).
_SPONSOR_TIER_FIT: dict[SponsorTier, float] = {
    SponsorTier.EXPLICIT_YES: 1.0,
    SponsorTier.REGISTRY_INFERRED: 0.75,
    SponsorTier.UNKNOWN: 0.40,
    SponsorTier.EXPLICIT_NO: 0.0,
}
# A job outside the relocation strategy keeps only this fraction of its tier fit.
OFF_STRATEGY_FACTOR = 0.5


def build_profile(text: str, *, target_countries: frozenset[str] = frozenset()) -> ResumeProfile:
    """Extract a structured profile from resume text using the shared job vocabulary."""
    return ResumeProfile(
        skills=extract_skills(text),
        categories=extract_categories(text),
        level=resolve_level(level_text=text, years_text=text),
        years=years_of_experience(text),
        target_countries=target_countries,
    )


def _skill_fit(
    profile: ResumeProfile, job: JobFacts
) -> tuple[float, frozenset[str], frozenset[str]]:
    """Coverage of the job's skills by the resume, plus the matched/missing breakdown.
    Coverage (not raw Jaccard) so a broad resume isn't penalised against a focused job."""
    matched = profile.skills & job.skills
    missing = job.skills - profile.skills
    fit = len(matched) / len(job.skills) if job.skills else 0.0
    return fit, matched, missing


def _category_fit(profile: ResumeProfile, job: JobFacts) -> float:
    if not job.categories:
        return 0.5  # the job gives no category signal — neutral, neither reward nor penalty
    return 1.0 if profile.categories & job.categories else 0.0


def _level_fit(profile: ResumeProfile, job: JobFacts) -> float:
    if profile.level is Level.UNSPECIFIED or job.level is Level.UNSPECIFIED:
        return LEVEL_UNKNOWN_FIT
    gap = LEVEL_SENIORITY[job.level] - LEVEL_SENIORITY[profile.level]
    penalty = LEVEL_STRETCH_PENALTY if gap > 0 else LEVEL_OVERQUALIFIED_PENALTY
    return max(0.0, 1.0 - penalty * abs(gap))


def _sponsor_fit(profile: ResumeProfile, job: JobFacts) -> float:
    fit = _SPONSOR_TIER_FIT[job.sponsor_tier]
    if profile.target_countries and job.country not in profile.target_countries:
        fit *= OFF_STRATEGY_FACTOR
    return fit


def score_match(profile: ResumeProfile, job: JobFacts) -> MatchScore:
    """Weighted, deterministic fit of a resume against one job's facts. Pure: same inputs
    always yield the same MatchScore (no clock, no IO)."""
    skill_fit, matched, missing = _skill_fit(profile, job)
    category_fit = _category_fit(profile, job)
    level_fit = _level_fit(profile, job)
    sponsor_fit = _sponsor_fit(profile, job)

    overall = (
        SKILL_WEIGHT * skill_fit
        + CATEGORY_WEIGHT * category_fit
        + LEVEL_WEIGHT * level_fit
        + SPONSOR_WEIGHT * sponsor_fit
    )
    return MatchScore(
        overall=round(100 * overall),
        skills_score=round(100 * skill_fit),
        level_score=round(100 * level_fit),
        sponsor_score=round(100 * sponsor_fit),
        matched_skills=matched,
        missing_skills=missing,
    )
