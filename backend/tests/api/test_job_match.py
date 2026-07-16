"""POST /jobs/{id}/match — the drawer's 'Assess fit' (§11 12e), now deterministic.

No overrides needed: the rationale is pure domain wording, so an unconfigured app (no key,
no budget) serves the full response. We prove the wiring, the concrete deterministic body,
repeatability, and the 404/422 edges.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import connect
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.api.app import create_app
from beacon.config import Settings
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob

NOW = datetime(2026, 7, 16, tzinfo=UTC)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "beacon.db"


@pytest.fixture
async def app_and_client(
    db_path: Path,
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    settings = Settings(db_path=db_path, seeds_path=Path("unused"))
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield app, http


def _seed_job(db_path: Path) -> int:
    conn = connect(db_path)
    company = SqliteCompanyRepo(conn).upsert(
        Company(name="Spotify", ats_type="lever", ats_slug="spotify", country_hq="SE", priority=1)
    )
    assert company.id is not None
    SqliteJobRepo(conn).upsert(
        company.id,
        NormalizedJob(
            source_id="lever",
            external_id="1",
            title="Senior iOS Engineer",
            url="https://example.test/1",
            description="Build the iOS app with Swift and SwiftUI. Kotlin a plus.",
            location_raw="Stockholm",
            country="SE",
            city="Stockholm",
            posted_at=NOW,
            content_hash="h1",
        ),
        seen_at=NOW,
    )
    job_id = int(conn.execute("SELECT id FROM jobs").fetchone()["id"])
    conn.close()
    return job_id


async def _create_resume(client: httpx.AsyncClient) -> int:
    body: dict[str, Any] = {
        "label": "CV",
        "text": "Senior iOS Engineer, 8 years of Swift and SwiftUI",
        "target_countries": ["SE"],
    }
    return int((await client.post("/resumes", json=body)).json()["id"])


async def test_assess_fit_returns_score_and_a_deterministic_rationale(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    _, client = app_and_client
    job_id = _seed_job(db_path)
    resume_id = await _create_resume(client)

    response = await client.post(f"/jobs/{job_id}/match?resume={resume_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["match_score"]["overall"] > 0
    # Concrete deterministic wording: kotlin is the one posting skill the resume lacks,
    # and the resume's SE relocation strategy matches the job's country.
    assert any("kotlin" in line for line in body["rationale"]["gaps"])
    assert body["rationale"]["sponsor_note"].endswith("SE is in your relocation strategy.")
    assert body["rationale"]["verdict"] == "Good fit — worth applying."


async def test_assess_fit_is_repeatable(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    _, client = app_and_client
    job_id = _seed_job(db_path)
    resume_id = await _create_resume(client)

    first = await client.post(f"/jobs/{job_id}/match?resume={resume_id}")
    second = await client.post(f"/jobs/{job_id}/match?resume={resume_id}")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()  # pure wording — no state, no drift


async def test_assess_fit_404s_for_unknown_job(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    _, client = app_and_client
    resume_id = await _create_resume(client)

    response = await client.post(f"/jobs/9999/match?resume={resume_id}")

    assert response.status_code == 404


async def test_assess_fit_404s_for_unknown_resume(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    _, client = app_and_client
    job_id = _seed_job(db_path)

    response = await client.post(f"/jobs/{job_id}/match?resume=9999")

    assert response.status_code == 404


async def test_assess_fit_requires_a_resume_param(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    _, client = app_and_client
    job_id = _seed_job(db_path)

    response = await client.post(f"/jobs/{job_id}/match")

    assert response.status_code == 422  # resume is a required query param
