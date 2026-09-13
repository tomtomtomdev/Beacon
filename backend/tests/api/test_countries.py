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


async def test_lists_every_market_including_the_home_row(client: httpx.AsyncClient) -> None:
    resp = await client.get("/countries")

    assert resp.status_code == 200
    assert len(resp.json()) == 12  # 11 relocation targets + the home market (SPEC §4)


async def test_home_row_leads_then_primary_tier_countries(client: httpx.AsyncClient) -> None:
    countries = (await client.get("/countries")).json()
    tiers = [c["priority_tier"] for c in countries]

    assert (countries[0]["code"], tiers[0]) == ("ID", "home")
    assert tiers[1] == "primary"
    assert tiers[-1] == "nice_to_have"


async def test_sweden_surfaces_its_reference_verbatim(client: httpx.AsyncClient) -> None:
    countries = {c["code"]: c for c in (await client.get("/countries")).json()}

    sweden = countries["SE"]
    assert "discontinued" in sweden["registry_name"].lower()
    assert "reform" in sweden["citizenship_summary"].lower()
    assert sweden["verified_at"] == "2026-01-15"
    assert sweden["source_url"].startswith("https://")
