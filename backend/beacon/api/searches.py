from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from beacon.api.deps import JobRepoDep, SearchRepoDep
from beacon.application.searches import (
    SearchSummary,
    create_search,
    delete_search,
    list_search_summaries,
    new_match_count,
)
from beacon.domain.saved_search import SavedSearch, SearchFilters

router = APIRouter()


class SearchFiltersDTO(BaseModel):
    q: str | None = None
    countries: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    tiers: list[str] = Field(default_factory=list)


class SearchCreate(BaseModel):
    name: str
    filters: SearchFiltersDTO = Field(default_factory=SearchFiltersDTO)
    notify_channel: str = "telegram"


class SearchOut(BaseModel):
    id: int
    name: str
    filters: SearchFiltersDTO
    notify_channel: str
    last_run_at: datetime | None
    new_count: int


@router.post("/searches", status_code=201)
def post_search(body: SearchCreate, searches: SearchRepoDep, jobs: JobRepoDep) -> SearchOut:
    created = create_search(
        searches,
        SavedSearch(
            name=body.name,
            filters=_to_domain_filters(body.filters),
            notify_channel=body.notify_channel,
        ),
    )
    return _to_out(SearchSummary(created, new_match_count(jobs, created.filters)))


@router.get("/searches")
def get_searches(searches: SearchRepoDep, jobs: JobRepoDep) -> list[SearchOut]:
    return [_to_out(summary) for summary in list_search_summaries(searches, jobs)]


@router.delete("/searches/{search_id}", status_code=204)
def delete_search_route(search_id: int, searches: SearchRepoDep) -> Response:
    if not delete_search(searches, search_id):
        raise HTTPException(status_code=404, detail="search not found")
    return Response(status_code=204)


def _to_domain_filters(dto: SearchFiltersDTO) -> SearchFilters:
    return SearchFilters(
        q=dto.q,
        countries=tuple(c.upper() for c in dto.countries),
        categories=tuple(dto.categories),
        levels=tuple(dto.levels),
        tiers=tuple(dto.tiers),
    )


def _filters_dto(filters: SearchFilters) -> SearchFiltersDTO:
    return SearchFiltersDTO(
        q=filters.q,
        countries=list(filters.countries),
        categories=list(filters.categories),
        levels=list(filters.levels),
        tiers=list(filters.tiers),
    )


def _to_out(summary: SearchSummary) -> SearchOut:
    search = summary.search
    if search.id is None:  # persisted rows always carry an id; guard narrows the type
        raise ValueError("saved search missing id")
    return SearchOut(
        id=search.id,
        name=search.name,
        filters=_filters_dto(search.filters),
        notify_channel=search.notify_channel,
        last_run_at=search.last_run_at,
        new_count=summary.new_count,
    )
