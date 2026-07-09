"""WWRAdapter — We Work Remotely RSS (XML), company-less. Title is 'Company: Role'."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.wwr import WWRAdapter
from beacon.application.ports import RawPosting

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def wwr_feed() -> str:
    return (FIXTURES / "wwr" / "feed.rss").read_text()


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> WWRAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return WWRAdapter(PoliteClient(client, min_interval=0.0))


async def parsed_items(wwr_feed: str) -> list[RawPosting]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=wwr_feed)

    return await make_adapter(handler).fetch()


async def test_wwr_fetch_parses_rss_items(wwr_feed: str) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, text=wwr_feed)

    items = await make_adapter(handler).fetch()

    assert seen_urls == ["https://weworkremotely.com/remote-jobs.rss"]
    assert len(items) == 3


async def test_wwr_normalize_splits_company_from_title(wwr_feed: str) -> None:
    items = await parsed_items(wwr_feed)
    job = make_adapter().normalize(items[0])

    assert job.source_id == "weworkremotely"
    assert job.company_name == "Acme Corp"
    assert job.title == "Senior Backend Engineer"
    assert job.url == "https://weworkremotely.com/remote-jobs/acme-corp-senior-backend-engineer"
    assert job.external_id  # a stable id (guid/link)
    assert job.posted_at == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    assert "senior backend engineer" in job.description.lower()
    assert "<p>" not in job.description  # HTML stripped


async def test_wwr_title_without_a_company_prefix(wwr_feed: str) -> None:
    items = await parsed_items(wwr_feed)
    job = make_adapter().normalize(items[2])

    # No "Company: Role" colon → whole title kept, no employer attributed.
    assert job.company_name is None
    assert job.title == "Standalone Product Designer"
    assert job.posted_at is None  # missing pubDate is never fabricated


async def test_wwr_normalize_every_item(wwr_feed: str) -> None:
    items = await parsed_items(wwr_feed)
    adapter = make_adapter()

    jobs = [adapter.normalize(item) for item in items]

    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)
