"""POST /jobs/{id}/match — the drawer's 'Assess fit' (§11 12e). The LLM boundary is faked via
dependency_overrides (the app is unconfigured for a key in tests); we prove the wiring, the
response shape, the single-job scope, the degrade-when-no-matcher path, and the 404/422 edges."""

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
from beacon.api.deps import get_matcher
from beacon.config import Settings
from beacon.domain.company import Company
from beacon.domain.job import NormalizedJob
from beacon.domain.resume import DeepMatchJob, MatchRationale, Resume

NOW = datetime(2026, 7, 16, tzinfo=UTC)

RATIONALE = MatchRationale(
    summary="Strong iOS fit.",
    strengths=("8 years Swift",),
    gaps=("No Kotlin",),
    verdict="Worth applying.",
    sponsor_note="Registry-inferred in a target country.",
)


class FakeMatcher:
    def __init__(self, rationale: MatchRationale) -> None:
        self._rationale = rationale
        self.calls: list[DeepMatchJob] = []

    def deep_match(self, resume: Resume, job: DeepMatchJob) -> MatchRationale:
        self.calls.append(job)
        return self._rationale


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


async def test_assess_fit_returns_score_and_rationale(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    app, client = app_and_client
    job_id = _seed_job(db_path)
    resume_id = await _create_resume(client)
    matcher = FakeMatcher(RATIONALE)
    app.dependency_overrides[get_matcher] = lambda: matcher

    response = await client.post(f"/jobs/{job_id}/match?resume={resume_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["match_score"]["overall"] > 0
    assert body["rationale"]["verdict"] == "Worth applying."
    assert body["rationale"]["strengths"] == ["8 years Swift"]
    assert len(matcher.calls) == 1  # exactly one job assessed


async def test_assess_fit_without_a_matcher_degrades_to_heuristic(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
    db_path: Path,
) -> None:
    app, client = app_and_client
    job_id = _seed_job(db_path)
    resume_id = await _create_resume(client)
    # No override: the unconfigured app resolves get_matcher to None (no Anthropic key).

    response = await client.post(f"/jobs/{job_id}/match?resume={resume_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["match_score"]["overall"] > 0  # heuristic score still returned
    assert body["rationale"] is None  # ...with no rationale, no crash


async def test_assess_fit_404s_for_unknown_job(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    app, client = app_and_client
    resume_id = await _create_resume(client)

    response = await client.post(f"/jobs/9999/match?resume={resume_id}")

    assert response.status_code == 404


async def test_assess_fit_404s_for_unknown_resume(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    app, client = app_and_client
    job_id = _seed_job(db_path)

    response = await client.post(f"/jobs/{job_id}/match?resume=9999")

    assert response.status_code == 404


async def test_assess_fit_requires_a_resume_param(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], db_path: Path
) -> None:
    app, client = app_and_client
    job_id = _seed_job(db_path)

    response = await client.post(f"/jobs/{job_id}/match")

    assert response.status_code == 422  # resume is a required query param
