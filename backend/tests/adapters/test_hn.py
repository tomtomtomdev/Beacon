import asyncio
from collections.abc import Callable, Mapping
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.hn import HNAdapter


@pytest.fixture
def hn_fixture(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("hn/whoishiring.json"))


def make_handler(
    fixture: dict[str, Any], seen_urls: list[str] | None = None
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen_urls is not None:
            seen_urls.append(str(request.url))
        path = request.url.path
        if path.endswith("/user/whoishiring.json"):
            return httpx.Response(200, json=fixture["user"])
        item_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        item = fixture["items"].get(item_id)
        if item is None:  # Firebase answers a purged item with the literal JSON `null`
            return httpx.Response(200, content=b"null")
        return httpx.Response(200, json=item)

    return handler


def make_adapter(
    fixture: dict[str, Any], *, concurrency: int = 10, seen_urls: list[str] | None = None
) -> HNAdapter:
    transport = httpx.MockTransport(make_handler(fixture, seen_urls))
    client = httpx.AsyncClient(transport=transport)
    return HNAdapter(PoliteClient(client, min_interval=0.0), concurrency=concurrency)


async def test_fetch_picks_the_who_is_hiring_thread_and_returns_only_real_postings(
    hn_fixture: dict[str, Any],
) -> None:
    adapter = make_adapter(hn_fixture)

    raw_postings = await adapter.fetch()

    # 2001/2002/2006 are real postings; deleted (2003), dead (2004), non-posting (2005)
    # and the missing item (2007) are all dropped. The freelancer/wants-hired threads and
    # last month's thread are never selected.
    assert sorted(str(raw["id"]) for raw in raw_postings) == ["2001", "2002", "2006"]


async def test_normalize_maps_a_posting_with_a_role_header(hn_fixture: dict[str, Any]) -> None:
    adapter = make_adapter(hn_fixture)
    raw_postings = await adapter.fetch()

    stripe = next(raw for raw in raw_postings if str(raw["id"]) == "2002")
    job = adapter.normalize(stripe)

    assert job.source_id == "hn"
    assert job.external_id == "2002"
    assert job.company_name == "Stripe"
    assert job.title == "Senior Backend Engineer"
    assert job.url == "https://news.ycombinator.com/item?id=2002"
    assert job.location_raw == "Remote (US)"
    assert job.posted_at is not None and job.posted_at.tzinfo is not None
    assert "payments infrastructure" in job.description
    assert "<p>" not in job.description  # HTML stripped


async def test_normalize_uses_company_as_title_when_header_has_no_role(
    hn_fixture: dict[str, Any],
) -> None:
    adapter = make_adapter(hn_fixture)
    raw_postings = await adapter.fetch()

    anthropic = next(raw for raw in raw_postings if str(raw["id"]) == "2001")
    job = adapter.normalize(anthropic)

    assert job.company_name == "Anthropic"
    assert job.title == "Anthropic"  # header carries no role keyword → fall back to company
    assert job.country == "US"  # "San Francisco, CA"
    assert "Visa sponsorship available" in job.description


async def test_re_poll_fetches_only_unseen_kids(hn_fixture: dict[str, Any]) -> None:
    seen_urls: list[str] = []
    adapter = make_adapter(hn_fixture, seen_urls=seen_urls)

    await adapter.fetch()
    seen_urls.clear()
    second = await adapter.fetch()

    # Same thread, no new kids: the re-poll re-checks the thread listing but fetches no
    # comment items (they are cached from the first poll).
    kid_item_requests = [u for u in seen_urls if "/item/2" in u]
    assert kid_item_requests == []
    assert second == []


class ConcurrencyProbe:
    """A Fetcher that records the peak number of concurrent in-flight item fetches."""

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._fixture = fixture
        self.max_in_flight = 0
        self._in_flight = 0

    async def get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        path = httpx.URL(url).path
        if path.endswith("/user/whoishiring.json"):
            return self._fixture["user"]
        item_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        self._in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self._in_flight)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self._in_flight -= 1
        return self._fixture["items"].get(item_id)


async def test_item_fetches_are_bounded_by_the_concurrency_limit(
    hn_fixture: dict[str, Any],
) -> None:
    probe = ConcurrencyProbe(hn_fixture)
    adapter = HNAdapter(probe, concurrency=3)

    await adapter.fetch()

    # Seven kids, limit 3 → never more than three comment fetches in flight at once.
    assert probe.max_in_flight == 3


class FlakyFetcher:
    """Fetcher that raises on one specific comment id; everything else uses the fixture."""

    def __init__(self, fixture: dict[str, Any], fail_id: str) -> None:
        self._fixture = fixture
        self._fail_id = fail_id
        self.item_requests: list[str] = []

    async def get_json(self, url: str, *, params: Mapping[str, str] | None = None) -> Any:
        path = httpx.URL(url).path
        if path.endswith("/user/whoishiring.json"):
            return self._fixture["user"]
        item_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        self.item_requests.append(item_id)
        if item_id == self._fail_id:
            raise httpx.ConnectError("boom")
        return self._fixture["items"].get(item_id)


async def test_a_raised_item_fetch_never_kills_the_poll_and_is_retried(
    hn_fixture: dict[str, Any],
) -> None:
    fetcher = FlakyFetcher(hn_fixture, fail_id="2002")
    adapter = HNAdapter(fetcher, concurrency=10)

    first = await adapter.fetch()
    fetcher.item_requests.clear()
    await adapter.fetch()

    # The failing comment is dropped from this poll but, being uncached, is fetched again.
    assert sorted(str(raw["id"]) for raw in first) == ["2001", "2006"]
    assert "2002" in fetcher.item_requests
