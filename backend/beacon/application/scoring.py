"""Tier-1 resume-fit scoring wired onto the /jobs page (§11 12c).

The pure scoring lives in domain.resume (score_match); this use case is the read-side glue:
it assembles JobFacts from the current page's read-model rows, then computes fit under a cache
keyed (resume_hash, content_hash). Scoring is deliberately bounded to the jobs handed in — the
current page — so a request never scans the whole table; the cache accumulates across page
visits so it still "covers" the whole DB over time, at $0 (Tier 1 is pure/deterministic).

Fit is a soft, opt-in signal like sponsorship: sort=match ranks by it, but the default sort is
untouched and no fit score ever filters a job out.
"""

from dataclasses import dataclass, replace
from datetime import datetime

from beacon.application.ports import (
    JobFilters,
    JobListing,
    JobPage,
    JobRepo,
    MatchScoreRepo,
)
from beacon.domain.classification import Category, Level
from beacon.domain.resume import JobFacts, MatchScore, Resume, score_match
from beacon.domain.sponsorship import SponsorTier
from beacon.domain.vocabulary import extract_skills


@dataclass(frozen=True, slots=True)
class ScorableJob:
    """A page job reduced to what scoring needs: its canonical id, its content_hash (the cache
    gate) and its assembled JobFacts."""

    id: int
    content_hash: str
    facts: JobFacts


def job_facts(
    *,
    categories: tuple[str, ...],
    level: str | None,
    country: str | None,
    sponsor_tier: str,
    description: str,
) -> JobFacts:
    """Assemble a job's scoring facts from its stored read-model fields plus its description (the
    skill source). Converts the stored strings to the domain enums score_match compares against.
    Shared by the list path (JobListing) and the deep-match path (JobDetail) — one assembly."""
    return JobFacts(
        skills=extract_skills(description),
        categories=frozenset(Category(value) for value in categories if value),
        level=Level(level) if level else Level.UNSPECIFIED,
        country=country,
        sponsor_tier=SponsorTier(sponsor_tier),
    )


def job_facts_from_listing(listing: JobListing, description: str) -> JobFacts:
    """A JobListing row + its description → JobFacts (the /jobs page scoring path)."""
    return job_facts(
        categories=listing.categories,
        level=listing.level,
        country=listing.country,
        sponsor_tier=listing.sponsor_tier,
        description=description,
    )


def score_jobs_for_resume(
    match_repo: MatchScoreRepo,
    resume: Resume,
    jobs: list[ScorableJob],
    *,
    now: datetime,
) -> dict[int, MatchScore]:
    """Fit scores for the page's jobs, cache-gated by (resume_hash, content_hash). A cached
    score whose content_hash still matches is reused (score_match not called); a miss or a
    changed posting recomputes just that job and refreshes the cache."""
    cached = match_repo.get_cached(resume.resume_hash, [job.id for job in jobs])
    scores: dict[int, MatchScore] = {}
    for job in jobs:
        hit = cached.get(job.id)
        if hit is not None and hit.content_hash == job.content_hash:
            scores[job.id] = hit.score
            continue
        score = score_match(resume.profile, job.facts)
        match_repo.upsert(resume.resume_hash, job.id, job.content_hash, score, now)
        scores[job.id] = score
    return scores


def list_scored_jobs(
    job_repo: JobRepo,
    match_repo: MatchScoreRepo,
    resume: Resume,
    filters: JobFilters,
    *,
    now: datetime,
) -> JobPage:
    """The /jobs page with a fit score attached to each row (SPEC §11 Tier 1). Scoring is
    bounded to the returned window. sort=match additionally re-orders that window by the fresh
    overall score, so the page is exact even when its cache was cold or stale (the SQL join in
    search() only biases which rows land in the window from a warm cache)."""
    page = job_repo.search(filters)
    inputs = job_repo.get_scoring_inputs([job.id for job in page.jobs])
    scorables = [
        ScorableJob(
            id=job.id,
            content_hash=inputs[job.id].content_hash,
            facts=job_facts_from_listing(job, inputs[job.id].description),
        )
        for job in page.jobs
        if job.id in inputs
    ]
    scores = score_jobs_for_resume(match_repo, resume, scorables, now=now)
    scored = [replace(job, match_score=scores.get(job.id)) for job in page.jobs]
    if filters.sort == "match":
        scored.sort(
            key=lambda job: job.match_score.overall if job.match_score else -1, reverse=True
        )
    return JobPage(jobs=scored, total=page.total)
