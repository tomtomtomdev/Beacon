"""GET /companies/health — the source-health view (DESIGN §3). Summary counts + per-company
status, with unsupported-ATS seed rows shown as 'pending' and shadow rows excluded."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import connect
from beacon.api.app import create_app
from beacon.config import Settings
from beacon.domain.company import Company
from beacon.domain.health import FailureKind, Health, SourceHealth

LAST_OK = datetime(2026, 7, 1, 6, 0, tzinfo=UTC)


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


def _seed(db_path: Path) -> SqliteCompanyRepo:
    repo = SqliteCompanyRepo(connect(db_path))
    repo.upsert(Company("Healthy", "greenhouse", "healthy", "IE", 1))
    repo.upsert(Company("Sick", "lever", "sick", "US", 1))
    repo.upsert(Company("Dormant", "smartrecruiters", "dormant", "SG", 3))  # no adapter → pending
    repo.upsert(Company("Shadow", "none", "", "US", 5))  # shadow employer → excluded
    return repo


def _quarantine(repo: SqliteCompanyRepo) -> None:
    sick = repo.get_by_name("Sick")
    assert sick is not None and sick.id is not None
    repo.set_health(
        sick.id,
        SourceHealth(
            consecutive_failures=3,
            health=Health.QUARANTINED,
            reason=FailureKind.GONE,
            last_success_at=LAST_OK,
        ),
    )


async def test_health_view_summarizes_and_lists_seed_companies(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    repo = _seed(db_path)
    _quarantine(repo)

    body = (await client.get("/companies/health")).json()

    summary = body["summary"]
    assert summary["seed"] == 3  # shadow row excluded
    assert summary["supported"] == 2  # greenhouse + lever have adapters
    assert summary["healthy"] == 1
    assert summary["quarantined"] == 1
    assert summary["pending"] == 1  # the smartrecruiters seed
    assert summary["by_ats"] == {"greenhouse": 1, "lever": 1, "smartrecruiters": 1}

    by_name = {row["name"]: row for row in body["companies"]}
    assert set(by_name) == {"Healthy", "Sick", "Dormant"}
    assert by_name["Sick"]["status"] == "quarantined"
    assert by_name["Sick"]["reason"] == "gone"
    assert by_name["Sick"]["last_success_at"].startswith("2026-07-01")
    assert by_name["Dormant"]["status"] == "pending"


async def test_pending_company_has_no_health_reason(
    client: httpx.AsyncClient, db_path: Path
) -> None:
    _seed(db_path)

    body = (await client.get("/companies/health")).json()

    dormant = next(row for row in body["companies"] if row["name"] == "Dormant")
    assert dormant["status"] == "pending"
    assert dormant["reason"] is None
