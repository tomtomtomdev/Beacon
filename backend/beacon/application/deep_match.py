"""Tier-2 deep match (§11 12e): score one job and explain it — deterministic, no LLM.

The heuristic score is computed fresh and build_rationale (domain/rationale.py) words the
SAME facts, so the explanation can never disagree with the score. Pure wording means it is
always available (no key), free (no budget), and never stale (no cache — a changed posting
simply re-derives). One job at a time; there is no whole-DB deep-match path.
"""

from dataclasses import dataclass

from beacon.application.ports import JobRepo
from beacon.application.scoring import job_facts
from beacon.domain.rationale import build_rationale
from beacon.domain.resume import MatchRationale, MatchScore, Resume, score_match


@dataclass(frozen=True, slots=True)
class DeepMatchResult:
    """The heuristic score for a job plus its deterministic Tier-2 rationale — always both;
    the generator is pure, so there is no skipped/failed state to represent."""

    score: MatchScore
    rationale: MatchRationale


def deep_match_job(job_repo: JobRepo, resume: Resume, job_id: int) -> DeepMatchResult | None:
    """Score one job against a resume and word its rationale. Returns None only when the
    job id is unknown (a 404 at the API); otherwise always a full DeepMatchResult."""
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
    return DeepMatchResult(score=score, rationale=build_rationale(resume.profile, facts, score))
