"""Teamtailor career sites publish a public JSON Feed at /jobs.json (no key) whose items
embed a schema.org JobPosting — recorded from Voi's board (Nordics coverage, SPEC §4 SE).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.teamtailor import TeamtailorAdapter


@pytest.fixture
def voi_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("teamtailor/voi_jobs.json"))


@pytest.fixture
def edge_jobs(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("teamtailor/edge_jobs.json"))


def make_adapter(
    slug: str = "careers.voi.com", handler: Callable[[httpx.Request], httpx.Response] | None = None
) -> TeamtailorAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return TeamtailorAdapter(slug=slug, fetcher=PoliteClient(client, min_interval=0.0))


def item(voi_jobs: dict[str, Any], title: str) -> dict[str, Any]:
    return next(i for i in voi_jobs["items"] if i["title"] == title)


def test_teamtailor_normalize_stockholm_posting(voi_jobs: dict[str, Any]) -> None:
    job = make_adapter().normalize(item(voi_jobs, "Senior Machine Learning Engineer"))

    assert job.source_id == "teamtailor"
    assert job.external_id == "ed4f8ab5-f70d-4a5d-aa0a-ca10251ea928"
    assert job.title == "Senior Machine Learning Engineer"
    assert job.url == "https://careers.voi.com/jobs/8254522-senior-machine-learning-engineer"
    assert job.country == "SE"  # schema.org addressCountry is already ISO-2
    assert job.city == "Stockholm"
    assert job.location_raw == "Stockholm, Sweden"
    # '2026-08-21T15:15:52+02:00' (Stockholm summer time) → aware UTC
    assert job.posted_at == datetime(2026, 8, 21, 13, 15, 52, tzinfo=UTC)
    assert job.company_name is None  # per-company source
    assert "<p>" not in job.description
    assert job.content_hash


def test_teamtailor_remote_posting_without_a_place_fabricates_nothing(
    edge_jobs: dict[str, Any],
) -> None:
    job = make_adapter().normalize(edge_jobs["items"][0])

    assert job.country is None
    assert job.city is None
    assert job.location_raw == ""
    assert job.posted_at is None
    assert job.description == "Java & Spring backend, work from anywhere."


def test_teamtailor_normalize_handles_every_recorded_item(voi_jobs: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in voi_jobs["items"]]

    assert len(jobs) == len(voi_jobs["items"])
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)


@pytest.mark.parametrize(
    ("slug", "expected_url"),
    [
        ("careers.voi.com", "https://careers.voi.com/jobs.json"),
        ("tibber", "https://tibber.teamtailor.com/jobs.json"),
    ],
    ids=["custom-career-domain", "bare-tenant-slug"],
)
async def test_teamtailor_fetch_accepts_a_domain_or_a_tenant_slug(
    voi_jobs: dict[str, Any], slug: str, expected_url: str
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=voi_jobs)

    raw_postings = await make_adapter(slug=slug, handler=handler).fetch()

    assert seen == [expected_url]
    assert len(raw_postings) == len(voi_jobs["items"])
