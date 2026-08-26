"""Rippling ATS per-company board — recorded from the public
`api.rippling.com/platform/api/ats/v1/board/{slug}/jobs` endpoint (rippling's own board).

Two-step by necessity: the board list carries no ad text, so each posting needs a detail
GET before it has a description (and therefore a content_hash, a sponsorship tier and a
resume score) — the same honest cost slice 13 accepted for SmartRecruiters and Workday.
The list also repeats a posting once per work location, so the uuid is the identity.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.rippling import RipplingAdapter

_BOARD = "https://api.rippling.com/platform/api/ats/v1/board/rippling/jobs"
_TORONTO = "1f81bd71-a3b5-4b91-aa6c-9999417a4c47"
_LONDON = "ba72246f-b46e-45da-9aec-3db244c2a35a"


@pytest.fixture
def board(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("rippling/board_jobs.json"))


@pytest.fixture
def details(load_fixture: Callable[[str], Any]) -> dict[str, dict[str, Any]]:
    return {
        _TORONTO: cast(dict[str, Any], load_fixture(f"rippling/job_{_TORONTO[:8]}.json")),
        _LONDON: cast(dict[str, Any], load_fixture(f"rippling/job_{_LONDON[:8]}.json")),
    }


def make_adapter(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    slug: str = "rippling",
) -> RipplingAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return RipplingAdapter(slug, PoliteClient(client, min_interval=0.0))


def board_handler(
    board: list[dict[str, Any]], details: dict[str, dict[str, Any]], calls: list[str]
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if url == _BOARD:
            return httpx.Response(200, json=board)
        uuid = url.rsplit("/", 1)[-1]
        detail = details.get(uuid)
        return httpx.Response(200, json=detail) if detail else httpx.Response(404, json={})

    return handler


async def test_rippling_fetch_dedupes_the_list_and_fetches_one_detail_each(
    board: list[dict[str, Any]], details: dict[str, dict[str, Any]]
) -> None:
    calls: list[str] = []

    raw_postings = await make_adapter(handler=board_handler(board, details, calls)).fetch()

    # 5 list rows, 3 uuids — a posting open in three cities is one job, not three.
    assert calls[0] == _BOARD
    assert len(calls) == 4  # the board, then one detail per unique uuid
    assert len(raw_postings) == 2  # the third uuid's detail 404s and is dropped, not fatal


async def test_rippling_normalize_reads_the_detail_payload(
    board: list[dict[str, Any]], details: dict[str, dict[str, Any]]
) -> None:
    adapter = make_adapter(handler=board_handler(board, details, []))
    raw_postings = await adapter.fetch()

    toronto = next(r for r in raw_postings if r["uuid"] == _TORONTO)
    normalized = adapter.normalize(toronto)

    assert normalized.source_id == "rippling"
    assert normalized.external_id == _TORONTO
    assert normalized.title == "Senior Software Engineer, Backend - Financial Product"
    assert normalized.url == f"https://ats.rippling.com/rippling/jobs/{_TORONTO}"
    assert normalized.company_name is None  # per-company source
    assert "<p>" not in normalized.description
    assert "Rippling" in normalized.description
    assert normalized.content_hash


async def test_rippling_first_work_location_decides_the_country(
    board: list[dict[str, Any]], details: dict[str, dict[str, Any]]
) -> None:
    adapter = make_adapter(handler=board_handler(board, details, []))
    raw_postings = await adapter.fetch()
    by_uuid = {r["uuid"]: adapter.normalize(r) for r in raw_postings}

    assert by_uuid[_TORONTO].location_raw == "San Francisco, CA; Toronto, Canada; Seattle, WA"
    assert (by_uuid[_TORONTO].country, by_uuid[_TORONTO].city) == ("US", "San Francisco")
    assert (by_uuid[_LONDON].country, by_uuid[_LONDON].city) == ("GB", "London")


async def test_rippling_created_on_keeps_its_offset_as_utc(
    board: list[dict[str, Any]], details: dict[str, dict[str, Any]]
) -> None:
    adapter = make_adapter(handler=board_handler(board, details, []))
    raw_postings = await adapter.fetch()

    london = adapter.normalize(next(r for r in raw_postings if r["uuid"] == _LONDON))

    # "2026-05-13T07:49:52.605000-07:00" is 14:49:52Z — the offset is honoured, not dropped.
    assert london.posted_at == datetime(2026, 5, 13, 14, 49, 52, 605000, tzinfo=UTC)


async def test_rippling_empty_board_is_a_successful_poll() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert await make_adapter(handler=handler).fetch() == []
