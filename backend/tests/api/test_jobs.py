import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import connect
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.api.app import create_app
from beacon.config import Settings
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

POLL_AT = datetime(2026, 7, 4, 6, 0, tzinfo=UTC)


def make_job(
    external_id: str,
    title: str,
    country: str | None,
    posted_at: datetime | None,
    description: str = "Build things.",
) -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse",
        external_id=external_id,
        title=title,
        url=f"https://example.test/{external_id}",
        description=description,
        location_raw="somewhere",
        country=country,
        city=None,
        posted_at=posted_at,
        content_hash=f"hash-{external_id}",
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "beacon.db"


@pytest.fixture
async def client(db_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(db_path=db_path, seeds_path=Path("unused"))
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


@pytest.fixture
def seeded(client: httpx.AsyncClient, db_path: Path) -> sqlite3.Connection:
    """Two companies, four jobs spanning countries, dates and sponsor tiers."""
    conn = connect(db_path)
    companies = SqliteCompanyRepo(conn)
    jobs = SqliteJobRepo(conn)
    spotify = companies.upsert(
        Company(name="Spotify", ats_type="lever", ats_slug="spotify", country_hq="SE", priority=1)
    )
    tines = companies.upsert(
        Company(name="Tines", ats_type="greenhouse", ats_slug="tines", country_hq="IE", priority=2)
    )
    assert spotify.id is not None and tines.id is not None

    jobs.upsert(
        spotify.id,
        make_job("1", "Swift Engineer", "SE", datetime(2026, 7, 1, tzinfo=UTC)),
        seen_at=POLL_AT,
    )
    jobs.upsert(
        spotify.id,
        make_job("2", "Data Engineer", "SE", datetime(2026, 7, 2, tzinfo=UTC)),
        seen_at=POLL_AT,
    )
    jobs.upsert(
        tines.id,
        make_job("3", "Swift Developer", "US", datetime(2026, 7, 3, tzinfo=UTC)),
        seen_at=POLL_AT,
    )
    jobs.upsert(tines.id, make_job("4", "Platform Engineer", "IE", None), seen_at=POLL_AT)
    return conn


async def get_jobs(client: httpx.AsyncClient, **params: Any) -> dict[str, Any]:
    response = await client.get("/jobs", params=params)
    assert response.status_code == 200, response.text
    payload: dict[str, Any] = response.json()
    return payload


async def test_jobs_api_filters(client: httpx.AsyncClient, seeded: sqlite3.Connection) -> None:
    payload = await get_jobs(client, q="swift", country="SE")

    assert payload["total"] == 1
    (job,) = payload["jobs"]
    assert job["title"] == "Swift Engineer"
    assert job["company"] == "Spotify"
    assert job["country"] == "SE"
    assert job["url"] == "https://example.test/1"


async def test_jobs_without_params_returns_every_job(
    client: httpx.AsyncClient, seeded: sqlite3.Connection
) -> None:
    payload = await get_jobs(client)

    assert payload["total"] == 4
    # equal sort_rank (all 'unknown') → newest posted_at first, null posted_at last
    assert [j["title"] for j in payload["jobs"]] == [
        "Swift Developer",
        "Data Engineer",
        "Swift Engineer",
        "Platform Engineer",
    ]


async def test_jobs_sorts_higher_sponsor_tier_first(
    client: httpx.AsyncClient, seeded: sqlite3.Connection
) -> None:
    seeded.execute("UPDATE jobs SET sponsor_tier = 'registry_inferred' WHERE external_id = '1'")
    seeded.execute("UPDATE jobs SET sponsor_tier = 'explicit_no' WHERE external_id = '3'")
    seeded.commit()

    payload = await get_jobs(client)

    titles = [j["title"] for j in payload["jobs"]]
    assert titles[0] == "Swift Engineer"  # registry_inferred outranks unknown
    assert titles[-1] == "Swift Developer"  # explicit_no sorts last but is still visible
    assert payload["total"] == 4


async def test_jobs_q_matches_description_too(
    client: httpx.AsyncClient, seeded: sqlite3.Connection
) -> None:
    seeded.execute("UPDATE jobs SET description = 'Kotlin and gRPC' WHERE external_id = '2'")
    seeded.commit()

    payload = await get_jobs(client, q="kotlin")

    assert [j["title"] for j in payload["jobs"]] == ["Data Engineer"]


async def test_jobs_limit_offset_paginate(
    client: httpx.AsyncClient, seeded: sqlite3.Connection
) -> None:
    first = await get_jobs(client, limit=2)
    second = await get_jobs(client, limit=2, offset=2)

    assert first["total"] == 4 and second["total"] == 4
    assert len(first["jobs"]) == 2 and len(second["jobs"]) == 2
    assert {j["id"] for j in first["jobs"]}.isdisjoint({j["id"] for j in second["jobs"]})


async def test_jobs_posted_since_excludes_older_and_undated(
    client: httpx.AsyncClient, seeded: sqlite3.Connection
) -> None:
    payload = await get_jobs(client, posted_since="2026-07-02T00:00:00+00:00")

    assert [j["title"] for j in payload["jobs"]] == ["Swift Developer", "Data Engineer"]


async def test_jobs_country_param_accepts_multiple_values(
    client: httpx.AsyncClient, seeded: sqlite3.Connection
) -> None:
    response = await client.get("/jobs", params=[("country", "SE"), ("country", "IE")])

    assert response.status_code == 200
    assert {j["country"] for j in response.json()["jobs"]} == {"SE", "IE"}
