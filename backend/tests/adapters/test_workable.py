"""Workable's public account widget (v1, details=true) against recorded SmartNews fixtures.

One call returns the whole board with descriptions inline — no per-posting detail fetch.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.workable import WorkableAdapter


@pytest.fixture
def smartnews_widget(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("workable/smartnews_widget.json"))


@pytest.fixture
def edge_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("workable/edge_jobs.json"))


def make_adapter(
    slug: str = "smartnews", handler: Callable[[httpx.Request], httpx.Response] | None = None
) -> WorkableAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return WorkableAdapter(slug=slug, fetcher=PoliteClient(client, min_interval=0.0))


def job_by_code(widget: dict[str, Any], shortcode: str) -> dict[str, Any]:
    return next(j for j in widget["jobs"] if j["shortcode"] == shortcode)


def test_workable_normalize_japanese_posting(smartnews_widget: dict[str, Any]) -> None:
    job = make_adapter().normalize(job_by_code(smartnews_widget, "0B21F4AE74"))

    assert job.source_id == "workable"
    assert job.external_id == "0B21F4AE74"
    assert job.title == "AI-First Product Designer 【AIファースト プロダクトデザイナー】"
    assert job.url == "https://apply.workable.com/j/0B21F4AE74"
    assert job.country == "JP"  # locations[].countryCode is the authoritative code
    assert job.city == "Shibuya"
    assert job.location_raw == "Shibuya, Tokyo, Japan"
    # published_on is a date with no clock — read as midnight UTC, never invented finer.
    assert job.posted_at == datetime(2026, 8, 7, tzinfo=UTC)
    assert job.company_name is None  # per-company source
    assert "<p>" not in job.description
    assert job.content_hash


def test_workable_absent_date_and_location_are_never_fabricated(edge_jobs: dict[str, Any]) -> None:
    job = make_adapter().normalize(edge_jobs["jobs"][0])

    assert job.posted_at is None
    assert job.country is None
    assert job.city is None
    assert job.location_raw == ""
    assert job.description == "Java & Spring Boot backend role, fully remote."


def test_workable_normalize_handles_every_recorded_job(smartnews_widget: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in smartnews_widget["jobs"]]

    assert len(jobs) == len(smartnews_widget["jobs"])
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)


async def test_workable_fetch_asks_the_widget_for_details(smartnews_widget: dict[str, Any]) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=smartnews_widget)

    raw_postings = await make_adapter(slug="smartnews", handler=handler).fetch()

    assert seen == ["https://apply.workable.com/api/v1/widget/accounts/smartnews?details=true"]
    assert len(raw_postings) == len(smartnews_widget["jobs"])
    assert all(raw["description"] for raw in raw_postings)
