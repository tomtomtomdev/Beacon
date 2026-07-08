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
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

POLL_AT = datetime(2026, 7, 8, 6, 0, tzinfo=UTC)

IOS_SE_SEARCH: dict[str, Any] = {
    "name": "Senior iOS",
    "filters": {"countries": ["SE", "NL"], "categories": ["ios"], "levels": ["senior"]},
    "notify_channel": "telegram",
}


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


def _seed_ios_job(db_path: Path, external_id: str, *, country: str, category: Category) -> None:
    conn = connect(db_path)
    company = SqliteCompanyRepo(conn).upsert(
        Company(name="Spotify", ats_type="lever", ats_slug="spotify", country_hq="SE", priority=1)
    )
    assert company.id is not None
    SqliteJobRepo(conn).upsert(
        company.id,
        NormalizedJob(
            source_id="lever",
            external_id=external_id,
            title="iOS Engineer",
            url=f"https://example.test/{external_id}",
            description="Build things.",
            location_raw=country,
            country=country,
            city=None,
            posted_at=None,
            content_hash=f"h-{external_id}",
        ),
        seen_at=POLL_AT,
        classification=Classification(categories=frozenset({category}), level=Level.SENIOR),
    )
    conn.close()


async def test_create_returns_201_with_id_and_echoed_filters(client: httpx.AsyncClient) -> None:
    response = await client.post("/searches", json=IOS_SE_SEARCH)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["name"] == "Senior iOS"
    assert body["filters"]["countries"] == ["SE", "NL"]
    assert body["filters"]["categories"] == ["ios"]
    assert body["notify_channel"] == "telegram"
    assert body["new_count"] == 0


async def test_list_returns_created_searches(client: httpx.AsyncClient) -> None:
    await client.post("/searches", json=IOS_SE_SEARCH)
    await client.post("/searches", json={"name": "Backend", "filters": {"categories": ["backend"]}})

    listed = (await client.get("/searches")).json()

    assert [s["name"] for s in listed] == ["Senior iOS", "Backend"]
    assert listed[1]["notify_channel"] == "telegram"  # server default when omitted


async def test_delete_returns_204_then_404(client: httpx.AsyncClient) -> None:
    created = (await client.post("/searches", json=IOS_SE_SEARCH)).json()

    assert (await client.delete(f"/searches/{created['id']}")).status_code == 204
    assert (await client.delete(f"/searches/{created['id']}")).status_code == 404
    assert (await client.get("/searches")).json() == []


async def test_new_count_counts_new_status_jobs_matching_the_filters(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed_ios_job(db_path, "1", country="SE", category=Category.IOS)  # matches
    _seed_ios_job(db_path, "2", country="NL", category=Category.IOS)  # matches
    _seed_ios_job(db_path, "3", country="US", category=Category.BACKEND)  # neither dimension

    await client.post("/searches", json=IOS_SE_SEARCH)
    listed = (await client.get("/searches")).json()

    assert listed[0]["new_count"] == 2
