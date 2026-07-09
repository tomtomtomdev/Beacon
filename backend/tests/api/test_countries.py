"""GET /countries serves the seeded visa reference. Seeding happens in the app lifespan,
so a fresh app already has the rows (no manual seed in the test)."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from beacon.api.app import create_app
from beacon.config import Settings


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(db_path=tmp_path / "beacon.db", seeds_path=Path("unused"))
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_lists_all_eleven_countries(client: httpx.AsyncClient) -> None:
    resp = await client.get("/countries")

    assert resp.status_code == 200
    assert len(resp.json()) == 11


async def test_primary_tier_countries_come_first(client: httpx.AsyncClient) -> None:
    tiers = [c["priority_tier"] for c in (await client.get("/countries")).json()]

    assert tiers[0] == "primary"
    assert tiers[-1] == "nice_to_have"


async def test_sweden_surfaces_its_reference_verbatim(client: httpx.AsyncClient) -> None:
    countries = {c["code"]: c for c in (await client.get("/countries")).json()}

    sweden = countries["SE"]
    assert "discontinued" in sweden["registry_name"].lower()
    assert "reform" in sweden["citizenship_summary"].lower()
    assert sweden["verified_at"] == "2026-01-15"
    assert sweden["source_url"].startswith("https://")
