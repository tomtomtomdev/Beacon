from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.domain.descriptions import content_hash, normalize_description


@pytest.fixture
def tines_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("greenhouse/tines_jobs.json"))


@pytest.fixture
def edge_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("greenhouse/edge_locations.json"))


def make_adapter(
    slug: str = "tines", handler: Callable[[httpx.Request], httpx.Response] | None = None
) -> GreenhouseAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return GreenhouseAdapter(slug=slug, client=client)


def test_greenhouse_normalize(tines_jobs: dict[str, Any]) -> None:
    adapter = make_adapter()
    raw = next(j for j in tines_jobs["jobs"] if j["id"] == 6000558004)

    job = adapter.normalize(raw)

    assert job.source_id == "greenhouse"
    assert job.external_id == "6000558004"
    assert job.title == "Content Marketing Manager"
    assert job.url == "https://job-boards.greenhouse.io/tines/jobs/6000558004"
    assert job.location_raw == "United States - East (Remote)"
    assert job.country == "US"
    assert job.city is None
    # '2026-05-19T20:17:51-04:00' converted to aware UTC
    assert job.posted_at == datetime(2026, 5, 20, 0, 17, 51, tzinfo=UTC)
    assert "Tines powers" in job.description
    assert "<" not in job.description and "&lt;" not in job.description
    assert job.content_hash == content_hash(normalize_description(raw["content"]))


def test_greenhouse_normalize_null_first_published_means_no_posted_at(
    edge_jobs: dict[str, Any],
) -> None:
    adapter = make_adapter()
    raw = next(j for j in edge_jobs["jobs"] if j["first_published"] is None)

    job = adapter.normalize(raw)

    assert job.posted_at is None


def test_greenhouse_normalize_handles_every_recorded_job(
    tines_jobs: dict[str, Any], edge_jobs: dict[str, Any]
) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in tines_jobs["jobs"] + edge_jobs["jobs"]]

    assert len(jobs) == len(tines_jobs["jobs"]) + len(edge_jobs["jobs"])
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)


async def test_greenhouse_fetch_uses_slug(tines_jobs: dict[str, Any]) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=tines_jobs)

    adapter = make_adapter(slug="tines", handler=handler)

    raw_postings = await adapter.fetch()

    assert seen_urls == ["https://boards-api.greenhouse.io/v1/boards/tines/jobs?content=true"]
    assert len(raw_postings) == 15
    assert all("id" in raw and "title" in raw for raw in raw_postings)
