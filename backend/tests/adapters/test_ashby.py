from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.ashby import AshbyAdapter
from beacon.domain.descriptions import content_hash, normalize_description

FULLSTACK = "d3bc1ced-3ce4-4086-a050-555055dbb1ff"


@pytest.fixture
def linear_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("ashby/linear_jobs.json"))


def make_adapter(
    slug: str = "linear", handler: Callable[[httpx.Request], httpx.Response] | None = None
) -> AshbyAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return AshbyAdapter(slug=slug, fetcher=PoliteClient(client, min_interval=0.0))


def test_ashby_normalize(linear_jobs: dict[str, Any]) -> None:
    raw = next(j for j in linear_jobs["jobs"] if j["id"] == FULLSTACK)

    job = make_adapter().normalize(raw)

    assert job.source_id == "ashby"
    assert job.external_id == FULLSTACK
    assert job.title == "Senior / Staff Fullstack Engineer"
    assert job.url == f"https://jobs.ashbyhq.com/linear/{FULLSTACK}"
    assert job.location_raw == "Europe"
    assert job.country is None and job.city is None  # "Europe" is a region
    assert job.posted_at == datetime(2021, 4, 27, 20, 13, 45, 158000, tzinfo=UTC)
    assert "Linear" in job.description
    assert "<" not in job.description and "&lt;" not in job.description
    assert job.content_hash == content_hash(normalize_description(raw["descriptionHtml"]))


def test_ashby_normalize_null_published_at(linear_jobs: dict[str, Any]) -> None:
    raw = next(j for j in linear_jobs["jobs"] if j["publishedAt"] is None)

    job = make_adapter().normalize(raw)

    assert job.posted_at is None  # board omitted publishedAt — never fabricated


def test_ashby_normalize_handles_every_recorded_job(linear_jobs: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in linear_jobs["jobs"]]

    assert len(jobs) == len(linear_jobs["jobs"])
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)


async def test_ashby_fetch_uses_slug(linear_jobs: dict[str, Any]) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=linear_jobs)

    raw_postings = await make_adapter(slug="linear", handler=handler).fetch()

    assert seen_urls == ["https://api.ashbyhq.com/posting-api/job-board/linear"]
    assert len(raw_postings) == 6
    assert all("id" in raw and "title" in raw for raw in raw_postings)
