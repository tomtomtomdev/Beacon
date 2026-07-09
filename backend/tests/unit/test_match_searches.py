from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pytest

from beacon.application.notify import match_saved_searches
from beacon.application.ports import (
    JobDetail,
    JobFilters,
    JobListing,
    JobPage,
)
from beacon.domain.classification import Classification
from beacon.domain.dedup import DedupRow
from beacon.domain.digest import Digest, HealthAlert
from beacon.domain.job import NormalizedJob
from beacon.domain.saved_search import SavedSearch, SearchFilters

NOW = datetime(2026, 7, 8, 6, 0, tzinfo=UTC)


def listing(
    job_id: int,
    *,
    title: str = "iOS Engineer",
    country: str | None = "SE",
    categories: tuple[str, ...] = ("ios",),
    level: str | None = "senior",
    tier: str = "registry_inferred",
) -> JobListing:
    return JobListing(
        id=job_id,
        title=title,
        company="Spotify",
        url=f"https://example.test/{job_id}",
        location_raw="Stockholm",
        country=country,
        city="Stockholm",
        categories=categories,
        level=level,
        posted_at=None,
        sponsor_tier=tier,
        user_status="new",
    )


class FakeJobRepo:
    """JobRepo whose search() returns a canned page keyed by the filter's keyword (q)."""

    def __init__(self, by_query: Mapping[str | None, list[JobListing]]) -> None:
        self._by_query = by_query

    def search(self, filters: JobFilters) -> JobPage:
        jobs = self._by_query.get(filters.q, [])
        return JobPage(jobs=jobs, total=len(jobs))

    def upsert(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError

    def content_hash_for(self, source_id: str, external_id: str) -> str | None:
        raise NotImplementedError

    def sweep_absent_jobs(
        self,
        source_id: str,
        company_id: int | None,
        seen_external_ids: set[str],
        now: datetime,
        *,
        threshold: int,
    ) -> int:
        raise NotImplementedError

    def list_unclassified(self) -> list[tuple[int, NormalizedJob]]:
        raise NotImplementedError

    def list_ambiguous(self) -> list[tuple[int, NormalizedJob]]:
        raise NotImplementedError

    def set_classification(self, job_id: int, classification: Classification) -> None:
        raise NotImplementedError

    def list_dedup_rows(self) -> list[DedupRow]:
        raise NotImplementedError

    def set_canonical_links(self, links: Mapping[int, int | None]) -> None:
        raise NotImplementedError

    def get_job_detail(self, job_id: int) -> JobDetail | None:
        raise NotImplementedError

    def set_user_status(self, job_id: int, status: str) -> int | None:
        raise NotImplementedError

    def resolve_registry_tier(self, company_id: int, tier: str) -> None:
        raise NotImplementedError


class FakeSearchRepo:
    def __init__(self, searches: list[SavedSearch]) -> None:
        self._searches = searches
        self._seen: dict[int, set[int]] = {}
        self.recorded: list[tuple[int, list[tuple[int, str]], datetime]] = []
        self.touched: list[tuple[int, datetime]] = []

    def with_seen(self, search_id: int, job_ids: set[int]) -> "FakeSearchRepo":
        self._seen[search_id] = set(job_ids)
        return self

    def list_all(self) -> list[SavedSearch]:
        return list(self._searches)

    def seen_job_ids(self, search_id: int) -> set[int]:
        return set(self._seen.get(search_id, set()))

    def record_matches(
        self, search_id: int, matches: Sequence[tuple[int, str]], notified_at: datetime
    ) -> None:
        self.recorded.append((search_id, list(matches), notified_at))
        self._seen.setdefault(search_id, set()).update(job_id for job_id, _ in matches)

    def touch_last_run(self, search_id: int, at: datetime) -> None:
        self.touched.append((search_id, at))

    def create(self, search: SavedSearch) -> SavedSearch:
        raise NotImplementedError

    def get(self, search_id: int) -> SavedSearch | None:
        raise NotImplementedError

    def delete(self, search_id: int) -> bool:
        raise NotImplementedError


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[Digest] = []

    async def send(self, digest: Digest) -> None:
        self.sent.append(digest)


class ExplodingNotifier:
    async def send(self, digest: Digest) -> None:
        raise RuntimeError("telegram unreachable")


def _search(name: str, filters: SearchFilters, search_id: int) -> SavedSearch:
    return SavedSearch(name=name, filters=filters, notify_channel="telegram", id=search_id)


IOS_SE = _search("Senior iOS", SearchFilters(q="ios", countries=("SE",), categories=("ios",)), 1)


async def test_notifies_one_grouped_digest_of_new_matches() -> None:
    searches = FakeSearchRepo([IOS_SE])
    jobs = FakeJobRepo({"ios": [listing(10), listing(11, title="Staff iOS")]})
    notifier = FakeNotifier()

    result = await match_saved_searches(searches, jobs, notifier, now=NOW)

    assert result.new_matches == 2
    assert len(notifier.sent) == 1
    (group,) = notifier.sent[0].groups
    assert group.search_name == "Senior iOS"
    assert [line.title for line in group.lines] == ["iOS Engineer", "Staff iOS"]


async def test_match_only_new_skips_already_notified_jobs() -> None:
    searches = FakeSearchRepo([IOS_SE]).with_seen(1, {10})
    jobs = FakeJobRepo({"ios": [listing(10), listing(11)]})
    notifier = FakeNotifier()

    result = await match_saved_searches(searches, jobs, notifier, now=NOW)

    assert result.new_matches == 1
    (group,) = notifier.sent[0].groups
    assert [line.url for line in group.lines] == ["https://example.test/11"]
    # Only the newly-matched job is recorded; the already-seen one is untouched.
    assert searches.recorded == [(1, [(11, "ios · SE")], NOW)]


async def test_match_reason_is_recorded_per_job() -> None:
    searches = FakeSearchRepo([IOS_SE])
    jobs = FakeJobRepo({"ios": [listing(10, country="SE", categories=("ios", "backend"))]})

    await match_saved_searches(searches, jobs, FakeNotifier(), now=NOW)

    assert searches.recorded == [(1, [(10, "ios · SE")], NOW)]


async def test_empty_digest_is_not_sent_but_last_run_is_touched() -> None:
    searches = FakeSearchRepo([IOS_SE])
    jobs = FakeJobRepo({"ios": []})
    notifier = FakeNotifier()

    result = await match_saved_searches(searches, jobs, notifier, now=NOW)

    assert result.new_matches == 0
    assert notifier.sent == []
    assert searches.recorded == []
    assert searches.touched == [(1, NOW)]  # the search still ran


async def test_health_alerts_send_a_digest_even_with_no_new_matches() -> None:
    searches = FakeSearchRepo([IOS_SE])
    jobs = FakeJobRepo({"ios": []})  # nothing matched
    notifier = FakeNotifier()
    alert = HealthAlert(company="crypto", reason="gone", since="never")

    result = await match_saved_searches(searches, jobs, notifier, now=NOW, health_alerts=(alert,))

    assert result.new_matches == 0
    assert notifier.sent[0].health_alerts == (alert,)  # the quarantine still notified
    assert searches.recorded == []  # no job matches recorded


async def test_send_failure_prevents_recording_so_matches_are_retried() -> None:
    searches = FakeSearchRepo([IOS_SE])
    jobs = FakeJobRepo({"ios": [listing(10)]})

    with pytest.raises(RuntimeError, match="telegram unreachable"):
        await match_saved_searches(searches, jobs, ExplodingNotifier(), now=NOW)

    assert searches.recorded == []  # nothing marked seen → re-notified next run
