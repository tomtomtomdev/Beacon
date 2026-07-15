"""/resumes API (§11 12b): paste-upload, list, set-active, delete."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from beacon.api.app import create_app
from beacon.config import Settings

IOS_RESUME: dict[str, Any] = {
    "label": "My CV",
    "text": "Senior iOS Engineer, 8 years of Swift and SwiftUI",
    "target_countries": ["nl", "se"],
}
BACKEND_RESUME: dict[str, Any] = {
    "label": "Backend CV",
    "text": "Backend engineer, Django Postgres",
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


async def test_paste_upload_returns_201_with_profile_and_active(client: httpx.AsyncClient) -> None:
    response = await client.post("/resumes", json=IOS_RESUME)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["label"] == "My CV"
    assert body["active"] is True
    assert body["profile"]["level"] == "senior"
    assert body["profile"]["years"] == 8
    assert body["profile"]["categories"] == ["ios"]
    assert {"swift", "swiftui"} <= set(body["profile"]["skills"])
    assert body["profile"]["target_countries"] == ["NL", "SE"]  # upper-cased codes


async def test_uploading_a_second_resume_makes_it_the_only_active(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/resumes", json=IOS_RESUME)
    await client.post("/resumes", json=BACKEND_RESUME)

    listed = (await client.get("/resumes")).json()

    assert [r["label"] for r in listed] == ["My CV", "Backend CV"]
    assert [r["active"] for r in listed] == [False, True]


async def test_reuploading_identical_text_dedupes_to_one_row(client: httpx.AsyncClient) -> None:
    first = (await client.post("/resumes", json=IOS_RESUME)).json()
    second = (await client.post("/resumes", json=IOS_RESUME)).json()

    listed = (await client.get("/resumes")).json()
    assert first["id"] == second["id"]
    assert len(listed) == 1


async def test_put_active_reactivates_and_404s_for_unknown(client: httpx.AsyncClient) -> None:
    first = (await client.post("/resumes", json=IOS_RESUME)).json()
    await client.post("/resumes", json=BACKEND_RESUME)  # steals active

    reactivated = await client.put(f"/resumes/{first['id']}/active")

    assert reactivated.status_code == 200
    assert reactivated.json()["active"] is True
    assert [r["active"] for r in (await client.get("/resumes")).json()] == [True, False]
    assert (await client.put("/resumes/9999/active")).status_code == 404


async def test_delete_returns_204_then_404(client: httpx.AsyncClient) -> None:
    created = (await client.post("/resumes", json=IOS_RESUME)).json()

    assert (await client.delete(f"/resumes/{created['id']}")).status_code == 204
    assert (await client.delete(f"/resumes/{created['id']}")).status_code == 404
    assert (await client.get("/resumes")).json() == []
