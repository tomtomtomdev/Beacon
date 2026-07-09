from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from beacon.api.app import create_app
from beacon.api.deps import get_http_client
from beacon.config import Settings


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "beacon.db"


@pytest.fixture
def telegram_calls() -> list[httpx.Request]:
    """Every request the test-send route makes to the (mocked) Telegram API."""
    return []


@pytest.fixture
def telegram_status() -> dict[str, int]:
    """Mutable so a test can force Telegram to reject the send."""
    return {"code": 200}


@pytest.fixture
async def client(
    db_path: Path, telegram_calls: list[httpx.Request], telegram_status: dict[str, int]
) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(db_path=db_path, seeds_path=Path("unused"))
    app = create_app(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        telegram_calls.append(request)
        code = telegram_status["code"]
        if code == 200:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(code, json={"ok": False, "description": "chat not found"})

    async def override_http_client() -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as mock:
            yield mock

    app.dependency_overrides[get_http_client] = override_http_client
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_get_returns_empty_settings_when_nothing_configured(
    client: httpx.AsyncClient,
) -> None:
    body = (await client.get("/settings/telegram")).json()

    assert body == {"chat_id": None, "bot_token_set": False}


async def test_put_persists_creds_and_get_reflects_them_without_leaking_the_token(
    client: httpx.AsyncClient,
) -> None:
    put = await client.put(
        "/settings/telegram", json={"chat_id": "4242", "bot_token": "123:secret"}
    )

    assert put.status_code == 200
    assert put.json() == {"chat_id": "4242", "bot_token_set": True}
    # The token is write-only: it must never come back over the wire.
    assert "123:secret" not in put.text
    get = (await client.get("/settings/telegram")).json()
    assert get == {"chat_id": "4242", "bot_token_set": True}


async def test_put_without_a_token_keeps_the_stored_token(client: httpx.AsyncClient) -> None:
    await client.put("/settings/telegram", json={"chat_id": "1", "bot_token": "keepme"})

    # A later save that changes only the chat_id (token omitted) must not clear the token.
    updated = (await client.put("/settings/telegram", json={"chat_id": "2"})).json()

    assert updated == {"chat_id": "2", "bot_token_set": True}


async def test_test_send_delivers_via_telegram_when_configured(
    client: httpx.AsyncClient, telegram_calls: list[httpx.Request]
) -> None:
    await client.put("/settings/telegram", json={"chat_id": "4242", "bot_token": "T"})

    result = await client.post("/settings/telegram/test")

    assert result.status_code == 200
    assert result.json() == {"ok": True, "channel": "telegram"}
    assert len(telegram_calls) == 1
    assert telegram_calls[0].url.path == "/botT/sendMessage"


async def test_test_send_falls_back_to_stdout_when_not_configured(
    client: httpx.AsyncClient, telegram_calls: list[httpx.Request]
) -> None:
    result = await client.post("/settings/telegram/test")

    assert result.json() == {"ok": True, "channel": "stdout"}
    assert telegram_calls == []  # nothing sent to Telegram


async def test_test_send_surfaces_the_telegram_error_as_400(
    client: httpx.AsyncClient, telegram_status: dict[str, int]
) -> None:
    await client.put("/settings/telegram", json={"chat_id": "bad", "bot_token": "T"})
    telegram_status["code"] = 400

    result = await client.post("/settings/telegram/test")

    assert result.status_code == 400
    assert result.json()["detail"] == "chat not found"


async def test_test_send_surfaces_a_network_failure_as_400_not_500(db_path: Path) -> None:
    # A connection failure reaching Telegram must read as a clean error, never a 500.
    settings = Settings(db_path=db_path, seeds_path=Path("unused"))
    app = create_app(settings)

    async def failing_client() -> AsyncIterator[httpx.AsyncClient]:
        def boom(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as mock:
            yield mock

    app.dependency_overrides[get_http_client] = failing_client
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            await http.put("/settings/telegram", json={"chat_id": "1", "bot_token": "T"})

            result = await http.post("/settings/telegram/test")

    assert result.status_code == 400
    assert "Could not reach Telegram" in result.json()["detail"]
