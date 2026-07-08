from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from beacon.api.deps import JobRepoDep
from beacon.application.ports import JobDetail, JobFilters, JobListing
from beacon.application.queries import get_job, list_jobs

router = APIRouter()


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


class JobsPageOut(BaseModel):
    jobs: list[JobOut]
    total: int


@router.get("/jobs")
def get_jobs(
    repo: JobRepoDep,
    q: str | None = None,
    country: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    level: Annotated[list[str] | None, Query()] = None,
    posted_since: datetime | None = None,
    sponsor_tier: Annotated[list[str] | None, Query()] = None,
    sort: Literal["tier", "date"] = "tier",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobsPageOut:
    if posted_since is not None and posted_since.tzinfo is None:
        posted_since = posted_since.replace(tzinfo=UTC)
    filters = JobFilters(
        q=q,
        countries=tuple(c.upper() for c in country or ()),
        categories=tuple(category or ()),
        levels=tuple(level or ()),
        posted_since=posted_since,
        sponsor_tiers=tuple(sponsor_tier or ()),
        sort=sort,
        limit=limit,
        offset=offset,
    )
    page = list_jobs(repo, filters)
    return JobsPageOut(jobs=[_to_dto(job) for job in page.jobs], total=page.total)


class DuplicateSourceOut(BaseModel):
    source: str
    company: str
    url: str


class JobDetailOut(JobOut):
    description: str
    duplicate_sources: list[DuplicateSourceOut]


@router.get("/jobs/{job_id}")
def get_job_detail(repo: JobRepoDep, job_id: int) -> JobDetailOut:
    detail = get_job(repo, job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_detail_dto(detail)


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
        description=detail.description,
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
    )
