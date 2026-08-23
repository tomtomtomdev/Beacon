"""Workday CxS (the career-site JSON behind every myworkdayjobs board) against recorded
Clio fixtures. The seed slug is "tenant/wdN/site"; search is POST-only, details are GET.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.workday import WorkdayAdapter

_SLUG = "clio/wd3/ClioCareerSite"
_CXS = "https://clio.wd3.myworkdayjobs.com/wday/cxs/clio/ClioCareerSite"


@pytest.fixture
def clio_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("workday/clio_jobs.json"))


@pytest.fixture
def clio_details(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("workday/clio_job_details.json"))


def make_adapter(
    slug: str = _SLUG,
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    page_limit: int = 20,
) -> WorkdayAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return WorkdayAdapter(
        slug=slug, fetcher=PoliteClient(client, min_interval=0.0), page_limit=page_limit
    )


def detail(clio_details: list[dict[str, Any]], title: str) -> dict[str, Any]:
    return next(d for d in clio_details if d["jobPostingInfo"]["title"] == title)


def test_workday_normalize_ml_posting(clio_details: list[dict[str, Any]]) -> None:
    job = make_adapter().normalize(detail(clio_details, "Machine Learning Engineer"))

    assert job.source_id == "workday"
    assert job.external_id == "be27448fb26a1001a12b0d92f5ff0000"
    assert job.title == "Machine Learning Engineer"
    assert job.url == (
        "https://clio.wd3.myworkdayjobs.com/ClioCareerSite/job/Vancouver/"
        "Machine-Learning-Engineer_BF-REQ-3169"
    )
    assert job.location_raw == "Vancouver, Canada"
    assert job.country == "CA"
    assert job.city == "Vancouver"
    # startDate is a bare date — midnight UTC, never a fabricated clock. postedOn ("Posted 4
    # Days Ago") is relative prose and deliberately ignored.
    assert job.posted_at == datetime(2026, 8, 19, tzinfo=UTC)
    assert job.company_name is None  # per-company source
    assert "Clio is the global leader" in job.description
    assert "<p>" not in job.description
    assert job.content_hash


def test_workday_normalize_maps_a_non_north_american_board(
    clio_details: list[dict[str, Any]],
) -> None:
    job = make_adapter().normalize(detail(clio_details, "Technical Trainer"))

    assert job.country == "GB"
    assert job.city == "London"


def test_workday_normalize_handles_every_recorded_posting(
    clio_details: list[dict[str, Any]],
) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in clio_details]

    assert len(jobs) == len(clio_details)
    assert all(j.external_id and j.title and j.url and j.description for j in jobs)


def test_workday_rejects_a_slug_that_is_not_tenant_site_shaped() -> None:
    with pytest.raises(ValueError, match="tenant/wdN/site"):
        make_adapter(slug="clio")


async def test_workday_fetch_posts_the_search_then_gets_each_detail(
    clio_jobs: dict[str, Any], clio_details: list[dict[str, Any]]
) -> None:
    posted_bodies: list[Any] = []
    detail_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posted_bodies.append(json.loads(request.content))
            return httpx.Response(200, json={**clio_jobs, "total": len(clio_jobs["jobPostings"])})
        detail_paths.append(request.url.path)
        title = request.url.path.rsplit("/", 1)[-1].split("_")[0].replace("-", " ")
        return httpx.Response(
            200,
            json=next(
                d
                for d in clio_details
                if d["jobPostingInfo"]["title"].lower().startswith(title.split()[0].lower())
            ),
        )

    raw_postings = await make_adapter(handler=handler).fetch()

    assert posted_bodies == [{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}]
    assert len(raw_postings) == 3
    assert all("jobPostingInfo" in raw for raw in raw_postings)
    assert detail_paths[0] == (
        "/wday/cxs/clio/ClioCareerSite/job/Vancouver/Machine-Learning-Engineer_BF-REQ-3169"
    )


async def test_workday_fetch_pages_the_search_until_total_is_covered() -> None:
    pages = {
        0: {"total": 3, "jobPostings": [{"externalPath": "/job/A"}, {"externalPath": "/job/B"}]},
        2: {"total": 3, "jobPostings": [{"externalPath": "/job/C"}]},
    }
    offsets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            offsets.append(body["offset"])
            return httpx.Response(200, json=pages[body["offset"]])
        path = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"jobPostingInfo": {"id": path, "title": path}})

    raw_postings = await make_adapter(handler=handler, page_limit=2).fetch()

    assert offsets == [0, 2]
    assert [raw["jobPostingInfo"]["id"] for raw in raw_postings] == ["A", "B", "C"]


async def test_workday_fetch_uses_the_cxs_base_built_from_the_slug(
    clio_jobs: dict[str, Any], clio_details: list[dict[str, Any]]
) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.method == "POST":
            return httpx.Response(
                200, json={"total": 1, "jobPostings": clio_jobs["jobPostings"][:1]}
            )
        return httpx.Response(200, json=clio_details[0])

    await make_adapter(handler=handler).fetch()

    assert urls[0] == f"{_CXS}/jobs"
    assert urls[1] == f"{_CXS}/job/Vancouver/Machine-Learning-Engineer_BF-REQ-3169"
