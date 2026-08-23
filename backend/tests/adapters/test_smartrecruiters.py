"""SmartRecruiters postings API (public, no auth) against recorded Grab fixtures.

The list endpoint omits the ad text, so fetch() pages the list and then GETs each
posting's detail — normalize() works on the detail payload.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.smartrecruiters import SmartRecruitersAdapter


@pytest.fixture
def grab_postings(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("smartrecruiters/grab_postings.json"))


@pytest.fixture
def grab_details(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("smartrecruiters/grab_posting_details.json"))


def make_adapter(
    slug: str = "Grab", handler: Callable[[httpx.Request], httpx.Response] | None = None
) -> SmartRecruitersAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return SmartRecruitersAdapter(slug=slug, fetcher=PoliteClient(client, min_interval=0.0))


def detail(grab_details: list[dict[str, Any]], posting_id: str) -> dict[str, Any]:
    return next(d for d in grab_details if d["id"] == posting_id)


def test_smartrecruiters_normalize_ios_posting(grab_details: list[dict[str, Any]]) -> None:
    job = make_adapter().normalize(detail(grab_details, "744000145029439"))

    assert job.source_id == "smartrecruiters"
    assert job.external_id == "744000145029439"
    assert job.title == "Software Engineer, iOS"
    assert job.url == "https://jobs.smartrecruiters.com/Grab/744000145029439-software-engineer-ios"
    assert job.country == "IN"  # location.country is lowercase ISO-2 in the payload
    assert job.city == "Bangalore"
    assert job.location_raw == "Bangalore, , India"
    assert job.posted_at == datetime(2026, 8, 23, 7, 44, 39, 357000, tzinfo=UTC)
    assert job.company_name is None  # per-company source: the seed row names the employer
    assert "<p>" not in job.description and "&nbsp;" not in job.description
    assert job.content_hash


def test_smartrecruiters_description_joins_every_ad_section(
    grab_details: list[dict[str, Any]],
) -> None:
    job = make_adapter().normalize(detail(grab_details, "744000145029439"))

    assert "About Grab and Our Workplace" in job.description  # companyDescription
    assert "Software Engineer, iOS to join" in job.description  # jobDescription
    # qualifications carry the skill keywords the classifier and resume matcher both read
    assert "Proficiency in Swift and Objective-C" in job.description
    assert "Life at Grab" in job.description  # additionalInformation


def test_smartrecruiters_normalize_handles_every_recorded_posting(
    grab_details: list[dict[str, Any]],
) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in grab_details]

    assert len(jobs) == len(grab_details)
    assert all(
        j.external_id and j.title and j.url and j.description and j.content_hash for j in jobs
    )


async def test_smartrecruiters_fetch_returns_detail_payloads_not_list_rows(
    grab_postings: dict[str, Any], grab_details: list[dict[str, Any]]
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        posting_id = request.url.path.rsplit("/", 1)[-1]
        if posting_id == "postings":
            return httpx.Response(200, json=grab_postings)
        return httpx.Response(200, json=detail(grab_details, posting_id))

    raw_postings = await make_adapter(handler=handler).fetch()

    assert len(raw_postings) == len(grab_postings["content"])
    # Every posting carries its ad text — the list alone never would.
    assert all(raw["jobAd"]["sections"] for raw in raw_postings)
    assert seen[0] == (
        "https://api.smartrecruiters.com/v1/companies/Grab/postings?limit=100&offset=0"
    )
    assert seen[1].endswith("/postings/744000145032469")


async def test_smartrecruiters_fetch_pages_until_total_found_is_covered() -> None:
    pages = {
        0: {"totalFound": 3, "content": [{"id": "1"}, {"id": "2"}]},
        2: {"totalFound": 3, "content": [{"id": "3"}]},
    }
    requested_offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/postings"):
            offset = request.url.params.get("offset", "0")
            requested_offsets.append(offset)
            return httpx.Response(200, json=pages[int(offset)])
        return httpx.Response(200, json={"id": request.url.path.rsplit("/", 1)[-1]})

    adapter = SmartRecruitersAdapter(
        slug="Grab",
        fetcher=PoliteClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler)), min_interval=0.0
        ),
        page_limit=2,
    )

    raw_postings = await adapter.fetch()

    assert requested_offsets == ["0", "2"]
    assert [raw["id"] for raw in raw_postings] == ["1", "2", "3"]
