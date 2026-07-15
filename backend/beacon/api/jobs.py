from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from beacon.api.deps import JobRepoDep, MatchScoreRepoDep, ResumeRepoDep
from beacon.application.ports import JobDetail, JobFilters, JobListing
from beacon.application.queries import get_job, list_jobs, set_job_status
from beacon.application.scoring import list_scored_jobs
from beacon.domain.resume import MatchScore
from beacon.domain.status import UserStatus

router = APIRouter()


class MatchScoreOut(BaseModel):
    """A resume's fit against one job (§11 Tier 1). Present only when the request names an
    active resume; a soft, opt-in signal — never a filter."""

    overall: int
    skills_score: int
    level_score: int
    sponsor_score: int
    matched_skills: list[str]
    missing_skills: list[str]


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    url: str
    location: str
    country: str | None
    city: str | None
    categories: list[str]
    level: str | None
    posted_at: datetime | None
    sponsor_tier: str
    user_status: UserStatus
    match_score: MatchScoreOut | None = None


class JobsPageOut(BaseModel):
    jobs: list[JobOut]
    total: int


@router.get("/jobs")
def get_jobs(
    repo: JobRepoDep,
    resumes: ResumeRepoDep,
    match_scores: MatchScoreRepoDep,
    q: str | None = None,
    country: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    level: Annotated[list[str] | None, Query()] = None,
    posted_since: datetime | None = None,
    sponsor_tier: Annotated[list[str] | None, Query()] = None,
    status: UserStatus | Literal["all"] | None = None,
    sort: Literal["tier", "date", "match"] = "tier",
    resume: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobsPageOut:
    if posted_since is not None and posted_since.tzinfo is None:
        posted_since = posted_since.replace(tzinfo=UTC)

    # ?resume=<id> attaches a fit score to each row (SPEC §11); an unknown id is a 404 so a
    # stale reference surfaces rather than silently returning unscored rows.
    active_resume = resumes.get(resume) if resume is not None else None
    if resume is not None and active_resume is None:
        raise HTTPException(status_code=404, detail="resume not found")

    filters = JobFilters(
        q=q,
        countries=tuple(c.upper() for c in country or ()),
        categories=tuple(category or ()),
        levels=tuple(level or ()),
        posted_since=posted_since,
        sponsor_tiers=tuple(sponsor_tier or ()),
        status=status,
        sort=sort,
        resume_hash=active_resume.resume_hash if active_resume else None,
        limit=limit,
        offset=offset,
    )
    if active_resume is not None:
        page = list_scored_jobs(repo, match_scores, active_resume, filters, now=datetime.now(UTC))
    else:
        page = list_jobs(repo, filters)
    return JobsPageOut(jobs=[_to_dto(job) for job in page.jobs], total=page.total)


class DuplicateSourceOut(BaseModel):
    source: str
    company: str
    url: str


class JobDetailOut(JobOut):
    description: str
    sponsor_evidence: str | None
    registries: list[str]
    match_confidence: float | None
    duplicate_sources: list[DuplicateSourceOut]


@router.get("/jobs/{job_id}")
def get_job_detail(repo: JobRepoDep, job_id: int) -> JobDetailOut:
    detail = get_job(repo, job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_detail_dto(detail)


class StatusUpdate(BaseModel):
    status: UserStatus


class StatusOut(BaseModel):
    id: int
    user_status: UserStatus


@router.patch("/jobs/{job_id}/status")
def patch_job_status(repo: JobRepoDep, job_id: int, body: StatusUpdate) -> StatusOut:
    canonical_id = set_job_status(repo, job_id, body.status.value)
    if canonical_id is None:
        raise HTTPException(status_code=404, detail="job not found")
    return StatusOut(id=canonical_id, user_status=body.status)


def _to_detail_dto(detail: JobDetail) -> JobDetailOut:
    return JobDetailOut(
        id=detail.id,
        title=detail.title,
        company=detail.company,
        url=detail.url,
        location=detail.location_raw,
        country=detail.country,
        city=detail.city,
        categories=list(detail.categories),
        level=detail.level,
        posted_at=detail.posted_at,
        sponsor_tier=detail.sponsor_tier,
        user_status=UserStatus(detail.user_status),
        description=detail.description,
        sponsor_evidence=detail.sponsor_evidence,
        registries=list(detail.registries),
        match_confidence=detail.match_confidence,
        duplicate_sources=[
            DuplicateSourceOut(source=s.source, company=s.company, url=s.url)
            for s in detail.duplicate_sources
        ],
    )


def _to_dto(job: JobListing) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        company=job.company,
        url=job.url,
        location=job.location_raw,
        country=job.country,
        city=job.city,
        categories=list(job.categories),
        level=job.level,
        posted_at=job.posted_at,
        sponsor_tier=job.sponsor_tier,
        user_status=UserStatus(job.user_status),
        match_score=_to_match_score(job.match_score),
    )


def _to_match_score(score: MatchScore | None) -> MatchScoreOut | None:
    if score is None:
        return None
    return MatchScoreOut(
        overall=score.overall,
        skills_score=score.skills_score,
        level_score=score.level_score,
        sponsor_score=score.sponsor_score,
        matched_skills=sorted(score.matched_skills),
        missing_skills=sorted(score.missing_skills),
    )
