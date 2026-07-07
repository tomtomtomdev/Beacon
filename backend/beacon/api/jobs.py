from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from beacon.api.deps import JobRepoDep
from beacon.application.ports import JobFilters, JobListing
from beacon.application.queries import list_jobs

router = APIRouter()


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    url: str
    location: str
    country: str | None
    city: str | None
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
        posted_since=posted_since,
        sponsor_tiers=tuple(sponsor_tier or ()),
        sort=sort,
        limit=limit,
        offset=offset,
    )
    page = list_jobs(repo, filters)
    return JobsPageOut(jobs=[_to_dto(job) for job in page.jobs], total=page.total)


def _to_dto(job: JobListing) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        company=job.company,
        url=job.url,
        location=job.location_raw,
        country=job.country,
        city=job.city,
        posted_at=job.posted_at,
        sponsor_tier=job.sponsor_tier,
    )
