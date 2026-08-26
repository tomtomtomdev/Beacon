"""NAV Norway (`pam-stilling-feed.nav.no`) as a company-less JobSource — recorded verbatim
from the live feed with NAV's public experimentation token. The token is never committed.

Norway's official register, the NO twin of JobTech, and the first source behind auth. The
recording pins the three things that make this feed different from every other source:
an INACTIVE item comes back with its title and employer *stripped*, the window is chosen
with If-Modified-Since, and the ad text needs a second call per posting.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.nav import NAVAdapter

_FEED = "https://pam-stilling-feed.nav.no/api/v1/feed"
_FULLSTACK = "5498f46d-4ae2-47c9-a15e-cbd2b78961b4"
_AI = "09652092-0b2c-4d9e-ae84-8e3475497b1a"
_CLOSED = "d5a741c1-88c2-48cb-a5be-f6ab16913361"
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def feed_page(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("nav/feed_page.json"))


@pytest.fixture
def entries(load_fixture: Callable[[str], Any]) -> dict[str, dict[str, Any]]:
    return {
        _FULLSTACK: cast(dict[str, Any], load_fixture("nav/entry_fullstack.json")),
        _AI: cast(dict[str, Any], load_fixture("nav/entry_ai.json")),
        _CLOSED: cast(dict[str, Any], load_fixture("nav/entry_closed.json")),
    }


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    max_pages: int = 1,
) -> NAVAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return NAVAdapter(PoliteClient(client, min_interval=0.0), max_pages=max_pages, now=lambda: NOW)


def feed_handler(
    feed_page: dict[str, Any],
    entries: dict[str, dict[str, Any]],
    calls: list[httpx.Request],
    pages: int = 1,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path.startswith("/api/v1/feedentry/"):
            return httpx.Response(200, json=entries[path.rsplit("/", 1)[-1]])
        served = sum(1 for c in calls if c.url.path.startswith("/api/v1/feed/")) + 1
        page = dict(feed_page)
        if served >= pages:  # the end of the feed says so with nulls
            page["next_url"] = None
            page["next_id"] = None
        return httpx.Response(200, json=page)

    return handler


async def test_nav_fetch_pins_the_window_it_wants(
    feed_page: dict[str, Any], entries: dict[str, dict[str, Any]]
) -> None:
    calls: list[httpx.Request] = []

    await make_adapter(handler=feed_handler(feed_page, entries, calls)).fetch()

    # The feed runs from 2019, so a poll that sent no window would walk seven years of ads.
    assert str(calls[0].url) == _FEED
    assert calls[0].headers["if-modified-since"] == "Sun, 23 Aug 2026 12:00:00 GMT"


async def test_nav_fetch_only_spends_a_detail_call_on_a_role_beacon_hunts(
    feed_page: dict[str, Any], entries: dict[str, dict[str, Any]]
) -> None:
    """~1% of this feed is software (measured: 48 tech-ish titles in 4,711 active ads over
    five days). Every ACTIVE ad is one detail call, so the title is filtered against the
    shared vocabulary first — the same "role families, not firehose" rule as Himalayas."""
    calls: list[httpx.Request] = []

    raw_postings = await make_adapter(handler=feed_handler(feed_page, entries, calls)).fetch()

    detail_paths = [c.url.path.rsplit("/", 1)[-1] for c in calls if "feedentry" in c.url.path]
    # Of 5 ACTIVE items, 3 name a role family; the cleaner and parking ads are never fetched.
    assert set(detail_paths) == {_FULLSTACK, _AI, _CLOSED}
    # ...and the one that closed between the two calls carries no ad_content, so it is dropped.
    assert [r["uuid"] for r in raw_postings] == [_FULLSTACK, _AI]


async def test_nav_normalize_reads_the_ad_content(
    feed_page: dict[str, Any], entries: dict[str, dict[str, Any]]
) -> None:
    adapter = make_adapter(handler=feed_handler(feed_page, entries, []))
    raw_postings = await adapter.fetch()

    normalized = adapter.normalize(next(r for r in raw_postings if r["uuid"] == _AI))

    assert normalized.source_id == "nav"
    assert normalized.external_id == _AI
    assert normalized.title.startswith("Lyst til å jobbe med AI")
    assert normalized.company_name == "Ansettr AS"  # company-less source names its employer
    assert normalized.url == f"https://arbeidsplassen.nav.no/stillinger/stilling/{_AI}"
    assert normalized.location_raw == "OSLO, NORGE"
    assert normalized.country == "NO"  # "NORGE" is the register's own Norwegian name
    assert normalized.city == "OSLO"
    assert normalized.posted_at == datetime(2026, 8, 25, 10, 34, 26, tzinfo=UTC)  # +02:00 → UTC
    assert "<p>" not in normalized.description
    assert normalized.content_hash


async def test_nav_fetch_follows_next_url_to_the_cap_and_says_so(
    feed_page: dict[str, Any],
    entries: dict[str, dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[httpx.Request] = []
    handler = feed_handler(feed_page, entries, calls, pages=5)

    with caplog.at_level("INFO"):
        await make_adapter(handler=handler, max_pages=2).fetch()

    feed_calls = [str(c.url) for c in calls if "feedentry" not in c.url.path]
    assert feed_calls == [_FEED, f"{_FEED}/78b41172-8236-4e41-a83f-3c36cb59fd0f"]
    assert "nav_page_cap" in caplog.text  # a partial sweep never reads as a complete one


async def test_nav_fetch_stops_when_the_feed_says_it_has_ended(
    feed_page: dict[str, Any], entries: dict[str, dict[str, Any]]
) -> None:
    calls: list[httpx.Request] = []

    await make_adapter(handler=feed_handler(feed_page, entries, calls), max_pages=9).fetch()

    # next_url/next_id null means "you are at the head of the feed" — not an error.
    assert [str(c.url) for c in calls if "feedentry" not in c.url.path] == [_FEED]


async def test_nav_fetches_a_repeated_uuid_only_once(
    feed_page: dict[str, Any], entries: dict[str, dict[str, Any]]
) -> None:
    """An ad edited twice inside the window appears on more than one page. Seen live on
    2026-08-26: the same feedentry was fetched twice in one poll."""
    calls: list[httpx.Request] = []
    handler = feed_handler(feed_page, entries, calls, pages=3)

    await make_adapter(handler=handler, max_pages=3).fetch()

    detail_paths = [c.url.path for c in calls if "feedentry" in c.url.path]
    assert len(detail_paths) == len(set(detail_paths))  # three identical pages, one call each
