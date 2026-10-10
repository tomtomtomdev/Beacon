"""Arbeitnow job-board API as a company-less JobSource — recorded live 2026-10-07 from
`/api/job-board-api?visa_sponsorship=true&page=1`, `data` trimmed to five representative rows
(city+country, remote, empty location, bare city, multi-city) with `links`/`meta` kept.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.arbeitnow import ArbeitnowAdapter

_API = "https://www.arbeitnow.com/api/job-board-api"


@pytest.fixture
def page1(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("arbeitnow/visa_sponsorship_page1.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None, max_pages: int = 3
) -> ArbeitnowAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return ArbeitnowAdapter(PoliteClient(client, min_interval=0.0), max_pages=max_pages)


def row(page1: dict[str, Any], slug: str) -> dict[str, Any]:
    return next(r for r in page1["data"] if r["slug"] == slug)


def test_arbeitnow_normalizes_a_recorded_posting(page1: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(row(page1, "ux-sdk-software-engineer-hamburg-254017"))

    assert normalized.source_id == "arbeitnow"
    assert normalized.external_id == "ux-sdk-software-engineer-hamburg-254017"
    assert normalized.title == "UX/SDK Software Engineer (f/m/d)"
    assert normalized.company_name == "Universalquantum"  # company-less source names its own
    # The arbeitnow URL is kept as the job link: the board's terms ask for a link back.
    assert normalized.url == (
        "https://www.arbeitnow.com/jobs/companies/universalquantum/"
        "ux-sdk-software-engineer-hamburg-254017"
    )
    assert normalized.location_raw == "Hamburg, Germany"
    assert normalized.country == "DE"
    assert normalized.city == "Hamburg"
    assert normalized.posted_at == datetime.fromtimestamp(1791361214, UTC)
    assert "<p>" not in normalized.description
    assert normalized.content_hash


@pytest.mark.parametrize(
    ("slug", "country", "city"),
    [
        # A remote row's location is a label, not a place: no country may be invented.
        ("remote-senior-ecommerce-growth-manager-all-genders-berlin-184011", None, "Remote job"),
        ("senior-ml-engineer-kimchi-llm-inference-optimization-195944", None, None),
        ("partnerships-lead-london-332861", "GB", "London"),
        # Several places that agree on a country name the country, never one city.
        ("remote-senior-ai-engineer-core-engine-408194", "DE", None),
    ],
    ids=["remote", "empty-location", "bare-city", "multi-city"],
)
def test_arbeitnow_reads_country_and_city_from_the_location_text(
    page1: dict[str, Any], slug: str, country: str | None, city: str | None
) -> None:
    normalized = make_adapter().normalize(row(page1, slug))

    assert (normalized.country, normalized.city) == (country, city)


def test_arbeitnow_normalize_handles_every_recorded_row(page1: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in page1["data"]]

    assert len(jobs) == len(page1["data"])
    assert all(j.external_id and j.title and j.company_name and j.content_hash for j in jobs)


def paged_handler(
    page1: dict[str, Any], requested: list[httpx.QueryParams], pages: int
) -> Callable[[httpx.Request], httpx.Response]:
    """Serves `pages` pages derived from the recorded one: same rows with page-suffixed
    slugs, and a `links.next` on every page but the last (as the live API paginates)."""

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.params)
        page = int(request.url.params["page"])
        data = [{**r, "slug": f"{r['slug']}-p{page}"} for r in page1["data"]]
        next_url = f"{request.url.copy_with(query=None)}?page={page + 1}" if page < pages else None
        return httpx.Response(200, json={**page1, "data": data, "links": {"next": next_url}})

    return handler


async def test_arbeitnow_walks_links_next_up_to_the_page_cap_and_logs_it(
    page1: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    requested: list[httpx.QueryParams] = []

    with caplog.at_level("INFO"):
        raw_postings = await make_adapter(paged_handler(page1, requested, pages=5), 2).fetch()

    assert [p["page"] for p in requested] == ["1", "2"]
    assert len(raw_postings) == 2 * len(page1["data"])
    assert "arbeitnow_page_cap" in caplog.text  # a partial sweep never reads as a complete one


async def test_arbeitnow_stops_when_links_next_is_null(
    page1: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    requested: list[httpx.QueryParams] = []

    with caplog.at_level("INFO"):
        await make_adapter(paged_handler(page1, requested, pages=2), 5).fetch()

    assert [p["page"] for p in requested] == ["1", "2"]
    assert "arbeitnow_page_cap" not in caplog.text


async def test_arbeitnow_requests_the_visa_sponsorship_subset(page1: dict[str, Any]) -> None:
    requested: list[httpx.QueryParams] = []

    await make_adapter(paged_handler(page1, requested, pages=1)).fetch()

    # A fetch filter only — it decides which postings Beacon ingests, never a tier: the rows
    # carry no per-posting visa field, so the tier is still read from text and registries.
    assert [p.get("visa_sponsorship") for p in requested] == ["true"]


async def test_arbeitnow_ingests_a_slug_once_when_new_postings_shift_the_pages(
    page1: dict[str, Any],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Newest-first paging: a posting published mid-walk pushes page 1's rows onto page 2,
        # so the same rows come back twice.
        page = int(request.url.params["page"])
        next_url = f"{_API}?page=2" if page == 1 else None
        return httpx.Response(200, json={**page1, "links": {"next": next_url}})

    raw_postings = await make_adapter(handler).fetch()

    assert len(raw_postings) == len(page1["data"])
