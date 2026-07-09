"""Notifier selection — the one place that decides Telegram vs Stdout. Shared by the
ingest CLI and the /settings/telegram/test route so both resolve a channel identically."""

import httpx

from beacon.adapters.notify.stdout import StdoutNotifier
from beacon.adapters.notify.telegram import TelegramNotifier
from beacon.application.ports import Notifier
from beacon.domain.notification import TelegramConfig


def make_notifier(config: TelegramConfig, client: httpx.AsyncClient) -> Notifier:
    """TelegramNotifier when both creds are present, else StdoutNotifier — so a poll or a
    test send never fails just because Telegram isn't configured yet."""
    token, chat_id = config.bot_token, config.chat_id
    if token and chat_id:
        return TelegramNotifier(client, bot_token=token, chat_id=chat_id)
    return StdoutNotifier()
