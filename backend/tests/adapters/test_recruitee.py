"""Recruitee per-company board — recorded from the public `{slug}.recruitee.com/api/offers/`
endpoint (channable, an NL seed). No auth. The `translations` blob (a per-locale copy of
description/requirements that nothing reads) is the only field dropped from the recording.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.recruitee import RecruiteeAdapter


@pytest.fixture
def offers(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("recruitee/offers.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    slug: str = "channable",
) -> RecruiteeAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return RecruiteeAdapter(slug, PoliteClient(client, min_interval=0.0))


def offer(offers: dict[str, Any], title: str) -> dict[str, Any]:
    return next(o for o in offers["offers"] if o["title"] == title)


def test_recruitee_normalize_reads_country_code_and_careers_url(offers: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(offer(offers, "Team Lead - Haskell Platform Team"))

    assert normalized.source_id == "recruitee"
    assert normalized.external_id == "2670943"
    assert normalized.title == "Team Lead - Haskell Platform Team"
    assert normalized.url == "https://jobs.channable.com/o/team-lead-haskell-platform-team"
    assert normalized.location_raw == "Utrecht, Utrecht, Netherlands"
    assert normalized.country == "NL"  # the board's own ISO-2, never parsed from text
    assert normalized.city == "Utrecht"
    assert normalized.company_name is None  # per-company source: the seed row names it
    assert normalized.content_hash


def test_recruitee_description_includes_the_requirements_section(offers: dict[str, Any]) -> None:
    """Recruitee splits one ad across `description` and `requirements`; the requirements half
    is where the tech stack and any sponsorship sentence live, so both are the description."""
    normalized = make_adapter().normalize(offer(offers, "Python Software Engineer -  AI team"))

    assert "<p>" not in normalized.description
    assert "Python" in normalized.description  # only in `description`
    assert "fast-growing B2B SaaS platform" in normalized.description  # only in `requirements`


def test_recruitee_published_at_parses_the_boards_own_utc_format(offers: dict[str, Any]) -> None:
    # "2026-06-02 10:10:41 UTC" — a space instead of T and a literal zone name.
    normalized = make_adapter().normalize(offer(offers, "Python Software Engineer -  AI team"))

    assert normalized.posted_at == datetime(2026, 6, 2, 10, 10, 41, tzinfo=UTC)


def test_recruitee_missing_publish_date_is_never_fabricated(offers: dict[str, Any]) -> None:
    raw = {**offer(offers, "Open application"), "published_at": None, "created_at": None}

    assert make_adapter().normalize(raw).posted_at is None


def test_recruitee_normalize_handles_every_recorded_offer(offers: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in offers["offers"]]

    assert len(jobs) == 4
    assert {j.country for j in jobs} == {"NL", "US", "DK"}
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)


async def test_recruitee_fetch_calls_the_company_board(offers: dict[str, Any]) -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json=offers)

    raw_postings = await make_adapter(handler=handler).fetch()

    assert urls == ["https://channable.recruitee.com/api/offers/"]
    assert len(raw_postings) == 4


async def test_recruitee_empty_board_is_a_successful_poll() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"offers": []})

    assert await make_adapter(handler=handler).fetch() == []
