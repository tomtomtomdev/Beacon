"""The Muse public jobs API as a company-less JobSource — recorded verbatim from
`/api/public/jobs?category=Software%20Engineering` (100,845 postings / 5,043 pages, no key).

The board ships `levels[]` and `locations[]` of its own, so the two things asserted hardest
here are the precedence rules: the board's level beats the title regex, and its synthetic
"Flexible / Remote" location is not a place.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.themuse import TheMuseAdapter
from beacon.domain.classification import Level


@pytest.fixture
def page1(load_fixture: Callable[[str], Any]) -> dict[str, Any]:
    return cast(dict[str, Any], load_fixture("themuse/jobs_page1.json"))


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    max_pages: int = 1,
) -> TheMuseAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return TheMuseAdapter(PoliteClient(client, min_interval=0.0), max_pages=max_pages)


def job(page1: dict[str, Any], company: str) -> dict[str, Any]:
    return next(r for r in page1["results"] if r["company"]["name"] == company)


def test_themuse_normalize_reads_the_boards_own_fields(page1: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(job(page1, "Uber"))

    assert normalized.source_id == "themuse"
    assert normalized.external_id == "21684771"  # the numeric id, not the slug
    assert normalized.title == "Agency Partner, Uber Advertising, Canada"
    assert normalized.company_name == "Uber"  # company-less source names its own employer
    assert normalized.url == (
        "https://www.themuse.com/jobs/uber/agency-partner-uber-advertising-canada"
    )
    assert normalized.location_raw == "Toronto, Canada"
    assert normalized.country == "CA"
    assert normalized.city == "Toronto"
    assert normalized.posted_at == datetime(2026, 7, 8, 0, 32, 52, tzinfo=UTC)
    assert "<p>" not in normalized.description  # HTML contents stripped
    assert normalized.content_hash


def test_themuse_board_level_wins_over_the_title(page1: dict[str, Any]) -> None:
    """ "Senior/Lead Software Engineer" would read LEAD off the title regex; the board says
    Senior Level, and the board's own metadata is the better signal (SPEC §5.2)."""
    senior = make_adapter().normalize(job(page1, "Exadel"))
    intern = make_adapter().normalize(job(page1, "GE Vernova"))

    assert senior.source_level is Level.SENIOR
    assert intern.source_level is Level.INTERN


def test_themuse_unmapped_board_level_leaves_the_title_to_decide(page1: dict[str, Any]) -> None:
    # "Mid Level" has no Beacon equivalent, and claiming UNSPECIFIED would *override* a
    # title that names a level. Only levels with a real equivalent are carried.
    mid = make_adapter().normalize(job(page1, "Riot Games"))

    assert mid.source_level is None


def test_themuse_first_real_location_wins_over_the_remote_sentinel(page1: dict[str, Any]) -> None:
    normalized = make_adapter().normalize(job(page1, "GlossGenius"))

    # "Flexible / Remote" is a filter value, not a place — the real office is the location.
    assert normalized.location_raw == "Flexible / Remote, New York, NY"
    assert normalized.country == "US"
    assert normalized.city == "New York"


def test_themuse_remote_only_posting_invents_no_country() -> None:
    raw = {
        "id": 1,
        "name": "Staff iOS Engineer",
        "contents": "<p>Remote</p>",
        "publication_date": "2026-08-01T00:00:00Z",
        "locations": [{"name": "Flexible / Remote"}],
        "levels": [],
        "company": {"name": "Acme"},
        "refs": {"landing_page": "https://www.themuse.com/jobs/acme/staff-ios-engineer"},
    }

    normalized = make_adapter().normalize(raw)

    assert normalized.location_raw == "Flexible / Remote"
    assert normalized.country is None
    assert normalized.city is None


def test_themuse_normalize_handles_every_recorded_posting(page1: dict[str, Any]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in page1["results"]]

    assert len(jobs) == len(page1["results"])
    assert all(j.external_id and j.title and j.company_name and j.content_hash for j in jobs)


async def test_themuse_fetch_asks_for_the_software_engineering_category(
    page1: dict[str, Any],
) -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=page1)

    raw_postings = await make_adapter(handler=handler).fetch()

    assert seen == [{"page": "1", "category": "Software Engineering"}]
    assert len(raw_postings) == len(page1["results"])


async def test_themuse_fetch_stops_at_the_last_page(page1: dict[str, Any]) -> None:
    pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pages.append(request.url.params["page"])
        return httpx.Response(200, json={**page1, "page": 1, "page_count": 1})

    await make_adapter(handler=handler, max_pages=5).fetch()

    assert pages == ["1"]  # page_count says there is nothing after this one


async def test_themuse_fetch_caps_the_walk_and_dedupes_by_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        results = [
            {
                "id": page * 100 + i,
                "name": "Software Engineer",
                "contents": "text",
                "locations": [],
                "levels": [],
                "company": {"name": "Acme"},
                "refs": {"landing_page": "https://www.themuse.com/jobs/acme/swe"},
            }
            for i in range(20)
        ]
        return httpx.Response(200, json={"page": page, "page_count": 5043, "results": results})

    with caplog.at_level("INFO"):
        raw_postings = await make_adapter(handler=handler, max_pages=2).fetch()

    assert len(raw_postings) == 40
    # 5,043 pages behind a 2-page cap: a partial sweep must never read as a complete one.
    assert "themuse_page_cap" in caplog.text
