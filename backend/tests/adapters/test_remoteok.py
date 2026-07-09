"""RemoteOKAdapter — public JSON API, company-less (each posting names its employer)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.remoteok import RemoteOKAdapter


@pytest.fixture
def remoteok_api(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("remoteok/api.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> RemoteOKAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return RemoteOKAdapter(PoliteClient(client, min_interval=0.0))


def posting(remoteok_api: list[dict[str, Any]], job_id: str) -> dict[str, Any]:
    return next(item for item in remoteok_api if item.get("id") == job_id)


def test_remoteok_normalize(remoteok_api: list[dict[str, Any]]) -> None:
    job = make_adapter().normalize(posting(remoteok_api, "1000001"))

    assert job.source_id == "remoteok"
    assert job.external_id == "1000001"
    assert job.title == "Senior iOS Engineer"
    assert job.company_name == "Acme"
    assert job.url == "https://remoteok.com/remote-jobs/1000001-senior-ios-engineer-acme"
    assert job.posted_at == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    assert "senior ios engineer" in job.description.lower()
    assert "<b>" not in job.description  # HTML stripped


def test_remoteok_parses_a_country_location(remoteok_api: list[dict[str, Any]]) -> None:
    job = make_adapter().normalize(posting(remoteok_api, "1000002"))

    assert job.country == "US"  # "United States" → US
    assert job.location_raw == "United States"


def test_remoteok_worldwide_and_region_locations_are_country_less(
    remoteok_api: list[dict[str, Any]],
) -> None:
    worldwide = make_adapter().normalize(posting(remoteok_api, "1000001"))
    europe = make_adapter().normalize(posting(remoteok_api, "1000003"))

    assert worldwide.country is None  # "Worldwide" is not a country
    assert europe.country is None  # "Europe" is a region, never a fabricated country
    assert europe.posted_at is None  # empty date is never fabricated


async def test_remoteok_fetch_drops_the_legal_notice_row(
    remoteok_api: list[dict[str, Any]],
) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=remoteok_api)

    postings = await make_adapter(handler).fetch()

    assert seen_urls == ["https://remoteok.com/api"]
    # The first array element is RemoteOK's legal-notice object (no id) — dropped.
    assert len(postings) == 3
    assert all("id" in p for p in postings)
