"""Saved-search queries used by the /searches API and shared with the notify pipeline.

The single place a SearchFilters is projected onto the /jobs query lives here so the
digest and the UI's 'N new' count can never drift apart."""

from dataclasses import dataclass

from beacon.application.ports import JobFilters, JobRepo, SearchRepo
from beacon.domain.saved_search import SavedSearch, SearchFilters
from beacon.domain.status import UserStatus

# A saved search alerts on its whole match set, not a paginated view.
MATCH_LIMIT = 500


def to_job_filters(
    filters: SearchFilters, *, status: str | None = None, limit: int = MATCH_LIMIT
) -> JobFilters:
    """Project saved-search criteria onto the canonical /jobs query. Sort/pagination are
    view concerns; status defaults to the standard view (everything except hidden)."""
    return JobFilters(
        q=filters.q,
        countries=filters.countries,
        categories=filters.categories,
        levels=filters.levels,
        sponsor_tiers=filters.tiers,
        status=status,
        limit=limit,
    )


@dataclass(frozen=True, slots=True)
class SearchSummary:
    """A saved search plus the count shown on its card: matching jobs the user hasn't
    triaged yet (user_status='new'), mirroring the nav's new-count semantics."""

    search: SavedSearch
    new_count: int


def new_match_count(jobs: JobRepo, filters: SearchFilters) -> int:
    return jobs.search(to_job_filters(filters, status=UserStatus.NEW.value, limit=1)).total


def create_search(searches: SearchRepo, search: SavedSearch) -> SavedSearch:
    return searches.create(search)


def list_search_summaries(searches: SearchRepo, jobs: JobRepo) -> list[SearchSummary]:
    return [SearchSummary(s, new_match_count(jobs, s.filters)) for s in searches.list_all()]


def delete_search(searches: SearchRepo, search_id: int) -> bool:
    return searches.delete(search_id)
