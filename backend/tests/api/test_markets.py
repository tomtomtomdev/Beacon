"""GET /markets — which countries actually hold open jobs, split by whether SPEC §4 assessed
them (slice 20c).

Its own endpoint rather than a field on /countries: that resource is the §4 visa reference,
seeded at startup and cached, and hanging a live job count off it would make a reference
resource change every poll.
"""

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

POLL_AT = datetime(2026, 9, 15, 5, 0, tzinfo=UTC)


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


def _seed(db_path: Path, counts: dict[str, int]) -> None:
    conn = connect(db_path)
    company = SqliteCompanyRepo(conn).upsert(Company("Tines", "greenhouse", "tines", "IE", 1))
    assert company.id is not None
    jobs = SqliteJobRepo(conn)
    for country, count in counts.items():
        for index in range(count):
            external_id = f"{country}-{index}"
            jobs.upsert(
                company.id,
                NormalizedJob(
                    source_id="greenhouse",
                    external_id=external_id,
                    title="Senior Backend Engineer",
                    url=f"https://greenhouse.test/{external_id}",
                    description="Build and operate distributed systems.",
                    location_raw=country,
                    country=country,
                    city=None,
                    posted_at=POLL_AT,
                    content_hash=f"hash-{external_id}",
                ),
                POLL_AT,
            )


async def _body(client: httpx.AsyncClient) -> dict[str, Any]:
    response = await client.get("/markets")
    assert response.status_code == 200
    return dict(response.json())


async def test_endpoint_reports_both_halves(client: httpx.AsyncClient, db_path: Path) -> None:
    """NL is assessed (§4 row); DE is not, and holds the fourth-largest block in the corpus."""
    _seed(db_path, {"NL": 2, "DE": 3})

    body = await _body(client)

    assert {"code": "NL", "open_jobs": 2} in body["target_markets"]
    assert body["other_markets"] == [{"code": "DE", "open_jobs": 3}]


async def test_endpoint_reports_zero_other_markets_on_an_empty_corpus(
    client: httpx.AsyncClient,
) -> None:
    """An empty list, not an absent key — the frontend must not have to tell the two apart."""
    body = await _body(client)

    assert body["other_markets"] == []


async def test_an_assessed_market_with_no_open_jobs_is_still_reported(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    """A target market is a reference fact. It keeps its menu row on a week with no postings,
    and the row states zero rather than disappearing."""
    _seed(db_path, {"DE": 1})

    body = await _body(client)

    assert {"code": "NL", "open_jobs": 0} in body["target_markets"]


async def test_other_markets_lead_with_the_largest(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed(db_path, {"DE": 1, "IN": 3, "TH": 2})

    body = await _body(client)

    assert [row["code"] for row in body["other_markets"]] == ["IN", "TH", "DE"]
