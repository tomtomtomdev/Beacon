"""TelegramNotifier — delivers a digest via the Bot API `sendMessage` (direct, no
Courier). Plain text (no parse_mode) so job titles with markdown-ish characters never
break rendering; long digests are split into ≤4096-char messages, one POST each."""

import httpx

from beacon.domain.digest import Digest, build_messages

# Telegram's per-message hard limit (Bot API sendMessage). The one place a digest is chunked.
TELEGRAM_MAX_CHARS = 4096
_API_BASE = "https://api.telegram.org"


class TelegramNotifier:
    def __init__(self, client: httpx.AsyncClient, *, bot_token: str, chat_id: str) -> None:
        self._client = client
        self._url = f"{_API_BASE}/bot{bot_token}/sendMessage"
        self._chat_id = chat_id

    async def send(self, digest: Digest) -> None:
        for message in build_messages(digest, max_chars=TELEGRAM_MAX_CHARS):
            response = await self._client.post(
                self._url, json={"chat_id": self._chat_id, "text": message}
            )
            response.raise_for_status()
