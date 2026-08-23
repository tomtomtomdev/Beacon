"""MyCareersFuture (Singapore's official government job board) as a company-less JobSource.

Search is POST-only and returns rows without ad text, so fetch() searches per role family and
then GETs each posting's detail; normalize() reads the detail payload.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.mycareersfuture import MyCareersFutureAdapter


@pytest.fixture
def search_ios(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("mycareersfuture/search_ios.json"))


@pytest.fixture
def job_details(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("mycareersfuture/job_details.json"))


@pytest.fixture
def edge_details(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("mycareersfuture/edge_job_details.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    queries: tuple[str, ...] = ("iOS engineer",),
    max_pages: int = 1,
) -> MyCareersFutureAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return MyCareersFutureAdapter(
        PoliteClient(client, min_interval=0.0), queries=queries, page_size=20, max_pages=max_pages
    )


def detail(job_details: list[dict[str, Any]], title: str) -> dict[str, Any]:
    return next(d for d in job_details if d["title"] == title)


def test_mycareersfuture_normalize_singapore_posting(job_details: list[dict[str, Any]]) -> None:
    job = make_adapter().normalize(detail(job_details, "iOS SDK Engineer"))

    assert job.source_id == "mycareersfuture"
    assert job.external_id == "a7fb9bf68a62114381c48b515abe95d7"
    assert job.title == "iOS SDK Engineer"
    assert job.company_name == "OZION TECH PTE. LTD."
    assert job.url == (
        "https://www.mycareersfuture.gov.sg/job/engineering/"
        "ios-sdk-engineer-ozion-tech-a7fb9bf68a62114381c48b515abe95d7"
    )
    assert job.country == "SG"
    assert job.city == "Singapore"
    assert job.location_raw == "Singapore"
    # newPostingDate is a bare date — midnight UTC, no invented clock.
    assert job.posted_at == datetime(2026, 8, 21, tzinfo=UTC)
    assert "Own the development of iOS SDKs" in job.description
    assert "<ul>" not in job.description
    assert job.content_hash


def test_mycareersfuture_overseas_posting_keeps_its_own_country(
    edge_details: list[dict[str, Any]],
) -> None:
    job = make_adapter().normalize(edge_details[0])

    assert job.country == "JP"  # address.isOverseas → overseasCountry, never SG
    assert job.city is None
    assert job.location_raw == "Japan"
    assert job.posted_at is None  # no posting date recorded → never fabricated


def test_mycareersfuture_normalize_handles_every_recorded_posting(
    job_details: list[dict[str, Any]],
) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in job_details]

    assert len(jobs) == len(job_details)
    assert all(j.external_id and j.title and j.company_name and j.description for j in jobs)


async def test_mycareersfuture_fetch_searches_each_query_then_gets_details(
    search_ios: dict[str, Any], job_details: list[dict[str, Any]]
) -> None:
    searches: list[dict[str, Any]] = []
    detail_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            searches.append(
                {"body": json.loads(request.content), "params": dict(request.url.params)}
            )
            return httpx.Response(200, json=search_ios)
        detail_paths.append(request.url.path)
        uuid = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=next(d for d in job_details if d["uuid"] == uuid))

    raw_postings = await make_adapter(handler=handler, queries=("iOS engineer", "Java")).fetch()

    assert [s["body"]["search"] for s in searches] == ["iOS engineer", "Java"]
    assert searches[0]["params"] == {"limit": "20", "page": "0"}
    # Both queries returned the same recorded rows; each uuid is fetched and ingested once.
    assert len(raw_postings) == len(search_ios["results"])
    assert len(detail_paths) == len(search_ios["results"])
    assert all(raw["description"] for raw in raw_postings)


async def test_mycareersfuture_fetch_stops_at_a_short_page(search_ios: dict[str, Any]) -> None:
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            pages.append(request.url.params["page"])
            return httpx.Response(200, json=search_ios)
        return httpx.Response(200, json={"uuid": "x", "title": "t", "description": "d"})

    await make_adapter(handler=handler, max_pages=4).fetch()

    assert pages == ["0"]  # three results on a 20-row page → no page 1
