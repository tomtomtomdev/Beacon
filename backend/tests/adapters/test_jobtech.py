from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.jobtech import JobTechAdapter


@pytest.fixture
def jobtech_search(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("jobtech/search.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> JobTechAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return JobTechAdapter(PoliteClient(client, min_interval=0.0))


def hit(jobtech_search: dict[str, Any], hit_id: str) -> dict[str, Any]:
    return next(h for h in jobtech_search["hits"] if h["id"] == hit_id)


def test_jobtech_normalize_swedish_hit(jobtech_search: dict[str, Any]) -> None:
    job = make_adapter().normalize(hit(jobtech_search, "31260112"))

    assert job.source_id == "jobtech"
    assert job.external_id == "31260112"
    assert job.title == "Senior Backend Engineer"
    assert job.company_name == "Spotify AB"
    assert job.country == "SE"  # numeric country_code 199 → SE
    assert job.city == "Stockholm"
    assert job.url == "https://arbetsformedlingen.se/platsbanken/annonser/31260112"
    # Naive publication_date is Swedish local time (CEST = UTC+2 in July) → aware UTC.
    assert job.posted_at == datetime(2026, 7, 1, 7, 0, tzinfo=UTC)
    assert "backend engineer" in job.description
    assert "<p>" not in job.description


def test_jobtech_defaults_country_to_se_when_absent(jobtech_search: dict[str, Any]) -> None:
    job = make_adapter().normalize(hit(jobtech_search, "31260110"))

    assert job.country == "SE"  # workplace_address had no country_code → board default
    assert job.city == "Göteborg"
    # Explicit +02:00 offset → aware UTC.
    assert job.posted_at == datetime(2026, 6, 15, 12, 30, tzinfo=UTC)


def test_jobtech_foreign_numeric_code_is_unknown_not_se(jobtech_search: dict[str, Any]) -> None:
    job = make_adapter().normalize(hit(jobtech_search, "31260107"))

    assert job.country is None  # code 155 (Norge) isn't Sweden and isn't mapped → not fabricated
    assert job.location_raw == "Oslo, Norge"  # raw preserved for a future better parser
    assert job.posted_at is None  # null publication_date is never fabricated
    # No webpage_url → the ad URL is reconstructed from the id.
    assert job.url == "https://arbetsformedlingen.se/platsbanken/annonser/31260107"


def test_jobtech_normalize_handles_every_recorded_hit(jobtech_search: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in jobtech_search["hits"]]

    assert len(jobs) == 4
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)
    assert all(j.company_name for j in jobs)  # company-less source: every job names its employer


async def test_jobtech_fetch_requests_the_search_endpoint(jobtech_search: dict[str, Any]) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=jobtech_search)

    raw_hits = await make_adapter(handler).fetch()

    assert seen_urls == ["https://jobsearch.api.jobtechdev.se/search?limit=100"]
    assert len(raw_hits) == 4
