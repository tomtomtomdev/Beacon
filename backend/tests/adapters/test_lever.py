from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.lever import LeverAdapter
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.vocabulary import extract_skills

GROWTH_LEAD = "8fcf6f7a-8cd4-45f8-a799-f731ca476b3a"
SUBSCRIPTIONS_IOS = "5089cbe3-5e62-4c24-89a2-9a1487eb5034"


@pytest.fixture
def immutable_jobs(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], load_fixture("lever/immutable_jobs.json"))


@pytest.fixture
def spotify_jobs(load_fixture: Callable[[str], Any]) -> list[dict[str, Any]]:
    """A full, untrimmed recording (2026-09-02): Lever splits a posting across `description`
    (the team blurb), `lists` (the requirement sections) and `additional`. immutable_jobs.json
    was recorded with those last two stripped, which is why no fixture test ever saw them."""
    return cast(list[dict[str, Any]], load_fixture("lever/spotify_jobs.json"))


def make_adapter(
    slug: str = "immutable", handler: Callable[[httpx.Request], httpx.Response] | None = None
) -> LeverAdapter:
    transport = httpx.MockTransport(handler) if handler else None
    client = httpx.AsyncClient(transport=transport)
    return LeverAdapter(slug=slug, fetcher=PoliteClient(client, min_interval=0.0))


def test_lever_normalize(immutable_jobs: list[dict[str, Any]]) -> None:
    raw = next(j for j in immutable_jobs if j["id"] == GROWTH_LEAD)

    job = make_adapter().normalize(raw)

    assert job.source_id == "lever"
    assert job.external_id == GROWTH_LEAD
    assert job.title == "Growth Lead"
    assert job.url == f"https://jobs.lever.co/immutable/{GROWTH_LEAD}"
    assert job.location_raw == "Sydney"
    assert job.country == "AU"  # Lever hands us an ISO-2 country directly
    assert job.city == "Sydney"
    # createdAt is epoch milliseconds → aware UTC.
    assert job.posted_at == datetime(2026, 4, 30, 9, 22, 4, 373000, tzinfo=UTC)
    assert "Immutable" in job.description
    assert "<" not in job.description and "&lt;" not in job.description
    assert job.content_hash == content_hash(normalize_description(raw["description"]))


def test_lever_normalize_null_created_at_and_country(immutable_jobs: list[dict[str, Any]]) -> None:
    raw = next(j for j in immutable_jobs if j["createdAt"] is None)

    job = make_adapter().normalize(raw)

    assert job.posted_at is None  # board omitted createdAt — never fabricated
    assert job.country is None  # no country field, "EMEA" is a region → no country
    assert job.location_raw == "EMEA"


def test_lever_normalize_handles_every_recorded_job(immutable_jobs: list[dict[str, Any]]) -> None:
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in immutable_jobs]

    assert len(jobs) == len(immutable_jobs)
    assert all(j.external_id and j.title and j.url and j.content_hash for j in jobs)


async def test_lever_fetch_uses_slug(immutable_jobs: list[dict[str, Any]]) -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=immutable_jobs)

    raw_postings = await make_adapter(slug="immutable", handler=handler).fetch()

    assert seen_urls == ["https://api.lever.co/v0/postings/immutable?mode=json"]
    assert len(raw_postings) == 4
    assert all("id" in raw and "text" in raw for raw in raw_postings)


def test_normalize_keeps_the_requirement_sections_lever_splits_out(
    spotify_jobs: list[dict[str, Any]],
) -> None:
    """The whole posting, not just its opening blurb. `description` is only Spotify's team
    intro; every skill a matcher reads ("Swift", "iOS") lives in `lists`, and dropping it left
    all 486 stored Lever jobs averaging 998 chars against 5,887 for Greenhouse."""
    raw = next(j for j in spotify_jobs if j["id"] == SUBSCRIPTIONS_IOS)

    job = make_adapter(slug="spotify").normalize(raw)

    assert "Swift" in job.description  # from lists[], absent from `description`
    assert "Who You Are" in job.description  # the section heading is kept as context
    assert len(job.description) > 3 * len(normalize_description(raw["description"]))
    assert "<" not in job.description and "&lt;" not in job.description


def test_normalize_extracts_skills_that_only_appear_in_the_requirement_sections(
    spotify_jobs: list[dict[str, Any]],
) -> None:
    """The user-visible bug: this posting scored 45 with zero matched skills, so a senior iOS
    resume read it as a non-match."""
    raw = next(j for j in spotify_jobs if j["id"] == SUBSCRIPTIONS_IOS)

    job = make_adapter(slug="spotify").normalize(raw)

    assert {"ios", "swift"} <= extract_skills(job.description)
    assert extract_skills(normalize_description(raw["description"])) == frozenset()


def test_normalize_handles_a_posting_recorded_without_lists(
    immutable_jobs: list[dict[str, Any]],
) -> None:
    """Lever omits `lists` on some postings ("Expression of Interest" carries none), so the
    composition must degrade to the blurb rather than raise."""
    adapter = make_adapter()

    jobs = [adapter.normalize(raw) for raw in immutable_jobs]

    assert all(job.description for job in jobs)
