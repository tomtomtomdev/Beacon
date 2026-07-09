"""Settings routes — read/update the Telegram creds and fire a live test message.

Secrets are write-only over the wire: the bot token is accepted on PUT but never
returned; GET reports only whether one is set (bot_token_set)."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from beacon.adapters.notify.factory import make_notifier
from beacon.api.deps import HttpClientDep, SettingsDep, SettingsRepoDep
from beacon.application.settings import (
    effective_telegram_config,
    send_test_message,
    update_telegram_config,
)
from beacon.domain.notification import TelegramConfig

router = APIRouter()


class TelegramSettingsOut(BaseModel):
    chat_id: str | None
    bot_token_set: bool  # whether a token is configured — the token itself is never returned


class TelegramSettingsUpdate(BaseModel):
    chat_id: str | None = None
    # None → keep the stored token (the UI doesn't re-send the secret); "" → clear; value → set.
    bot_token: str | None = None


class TestResult(BaseModel):
    ok: bool
    channel: str  # "telegram" when creds resolved, else "stdout" (printed to the server log)


def get_effective_config(repo: SettingsRepoDep, settings: SettingsDep) -> TelegramConfig:
    """The creds actually used to send: DB-set values layered over the env fallback."""
    return effective_telegram_config(repo, settings.telegram_config())


EffectiveConfigDep = Annotated[TelegramConfig, Depends(get_effective_config)]


@router.get("/settings/telegram")
def get_telegram_settings(config: EffectiveConfigDep) -> TelegramSettingsOut:
    return _out(config)


@router.put("/settings/telegram")
def put_telegram_settings(
    body: TelegramSettingsUpdate, repo: SettingsRepoDep, settings: SettingsDep
) -> TelegramSettingsOut:
    update_telegram_config(repo, chat_id=body.chat_id, bot_token=body.bot_token)
    return _out(effective_telegram_config(repo, settings.telegram_config()))


@router.post("/settings/telegram/test")
async def send_telegram_test(config: EffectiveConfigDep, client: HttpClientDep) -> TestResult:
    notifier = make_notifier(config, client)
    try:
        await send_test_message(notifier)
    except httpx.HTTPError as exc:
        # A rejected send (e.g. "chat not found") or a network failure reaching Telegram —
        # surface a readable reason to the UI instead of a 500.
        raise HTTPException(status_code=400, detail=_telegram_error(exc)) from exc
    return TestResult(ok=True, channel="telegram" if config.is_configured else "stdout")


def _out(config: TelegramConfig) -> TelegramSettingsOut:
    return TelegramSettingsOut(chat_id=config.chat_id, bot_token_set=bool(config.bot_token))


def _telegram_error(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            payload = exc.response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict) and payload.get("description"):
            return str(payload["description"])
        return f"Telegram returned HTTP {exc.response.status_code}"
    return f"Could not reach Telegram: {exc}"  # RequestError: connect/timeout/etc.
