"""Tier-2 LLM deep-match (§11 12e): an on-demand, budget-capped rationale for one job.

Mirrors the slice-9 tiered classifier's discipline. The heuristic (Tier-1) score is ALWAYS
computed and returned; the LLM only *upgrades* it with a rationale, and never for more than the
single job asked about. A cached rationale (same resume_hash + content_hash) is reused with no
call and no budget spend; an absent key (matcher=None), an exhausted budget, or ANY LLM error
degrades silently to the heuristic-only result. The LLM is an upgrader, never a dependency.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import JobRepo, LLMBudget, Matcher, MatchScoreRepo
from beacon.application.scoring import job_facts
from beacon.domain.resume import DeepMatchJob, MatchRationale, MatchScore, Resume, score_match

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeepMatchResult:
    """The heuristic score for a job plus its optional Tier-2 rationale. rationale is None when
    the deep match was skipped (no key / budget exhausted) or failed — the score always stands."""

    score: MatchScore
    rationale: MatchRationale | None


def deep_match_job(
    job_repo: JobRepo,
    match_repo: MatchScoreRepo,
    matcher: Matcher | None,
    budget: LLMBudget,
    resume: Resume,
    job_id: int,
    *,
    now: datetime,
) -> DeepMatchResult | None:
    """Score one job against a resume and, when possible, attach an LLM rationale. Returns None
    only when the job id is unknown (a 404 at the API); otherwise always a DeepMatchResult."""
    detail = job_repo.get_job_detail(job_id)
    if detail is None:
        return None
    scoring = job_repo.get_scoring_inputs([detail.id]).get(detail.id)
    if scoring is None:  # a canonical job with no stored content — nothing to score against
        return None

    facts = job_facts(
        categories=detail.categories,
        level=detail.level,
        country=detail.country,
        sponsor_tier=detail.sponsor_tier,
        description=scoring.description,
    )
    score = score_match(resume.profile, facts)

    cached = match_repo.get_rationale(resume.resume_hash, detail.id)
    if cached is not None and cached.content_hash == scoring.content_hash:
        return DeepMatchResult(score=score, rationale=cached.rationale)

    if matcher is None or not budget.try_reserve():
        return DeepMatchResult(score=score, rationale=None)

    context = DeepMatchJob(
        title=detail.title,
        description=scoring.description,
        country=detail.country,
        sponsor_tier=facts.sponsor_tier,
        heuristic=score,
    )
    try:
        rationale = matcher.deep_match(resume, context)
    except Exception:
        logger.warning(
            "deep_match_failed job_id=%s (kept heuristic score)", detail.id, exc_info=True
        )
        return DeepMatchResult(score=score, rationale=None)

    match_repo.upsert(resume.resume_hash, detail.id, scoring.content_hash, score, now)
    match_repo.set_rationale(resume.resume_hash, detail.id, scoring.content_hash, rationale, now)
    return DeepMatchResult(score=score, rationale=rationale)
