"""GET /registries — sponsor-registry coverage (DESIGN §1, the globe widget's second block).

The endpoint's job is to make an *absent* snapshot visible: a register with no row in
registries_meta has never been ingested on this box, and that is the state SPEC §4 asserted
away for sixteen slices."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import connect
from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo
from beacon.api.app import create_app
from beacon.config import Settings
from beacon.domain.company import Company
from beacon.domain.registry import REGISTRY_STALE_AFTER_DAYS, Registry


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


def _seed(db_path: Path) -> None:
    """Two registers ingested (IE, CA) and one company matched by both — the live shape on
    2026-09-15, where UK/NL/US have adapters, are wired into refresh, and have no snapshot."""
    conn = connect(db_path)
    companies = SqliteCompanyRepo(conn)
    for name, flags in (
        ("Tines", Registry.IE),
        ("Shopify", Registry.CA),
        ("Both", Registry.IE | Registry.CA),
    ):
        company = companies.upsert(Company(name, "greenhouse", name.lower(), "IE", 1))
        assert company.id is not None
        companies.set_registry_match(company.id, int(flags), 0.94, "seeded")
    meta = SqliteRegistriesMetaRepo(conn)
    meta.record("IE", datetime.now(UTC) - timedelta(days=11), 6360)
    meta.record("CA", datetime.now(UTC) - timedelta(days=REGISTRY_STALE_AFTER_DAYS + 1), 7884)


async def _rows(client: httpx.AsyncClient) -> dict[str, dict[str, Any]]:
    body = (await client.get("/registries")).json()
    return {row["registry"]: row for row in body["registries"]}


async def test_a_registry_with_no_snapshot_is_listed_as_never_ingested(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed(db_path)

    rows = await _rows(client)

    assert rows["UK"]["fetched_at"] is None
    assert rows["UK"]["row_count"] is None
    assert rows["UK"]["companies"] == 0


async def test_every_registry_bit_is_listed_and_the_hand_flag_is_not(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed(db_path)

    rows = await _rows(client)

    assert set(rows) == {r.name for r in Registry} - {Registry.MANUAL.name}


async def test_an_ingested_snapshot_reports_its_rows_and_matches(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed(db_path)

    rows = await _rows(client)

    assert rows["IE"]["row_count"] == 6360
    assert rows["IE"]["companies"] == 2  # Tines + the company matched by both
    assert rows["IE"]["stale"] is False
    assert rows["CA"]["companies"] == 2


async def test_a_snapshot_past_the_window_is_flagged_stale(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed(db_path)

    rows = await _rows(client)

    assert rows["CA"]["stale"] is True
