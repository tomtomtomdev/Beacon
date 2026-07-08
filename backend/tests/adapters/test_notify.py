import json

import httpx
import pytest

from beacon.adapters.notify.stdout import StdoutNotifier
from beacon.adapters.notify.telegram import TELEGRAM_MAX_CHARS, TelegramNotifier
from beacon.domain.digest import Digest, DigestGroup, DigestLine


def _line(title: str) -> DigestLine:
    return DigestLine(
        title=title,
        company="Spotify",
        country="SE",
        tier="registry_inferred",
        url=f"https://example.test/{title}",
        reason="ios · SE",
    )


def _digest(*titles: str) -> Digest:
    return Digest(groups=(DigestGroup("Senior iOS", tuple(_line(t) for t in titles)),))


def test_telegram_limit_matches_the_bot_api() -> None:
    assert TELEGRAM_MAX_CHARS == 4096


async def test_sends_one_plain_text_post_per_message() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    notifier = TelegramNotifier(client, bot_token="SECRET-TOKEN", chat_id="4242")

    await notifier.send(_digest("iOS Engineer"))

    assert len(seen) == 1
    request = seen[0]
    assert request.url.path == "/botSECRET-TOKEN/sendMessage"
    body = json.loads(request.content)
    assert body["chat_id"] == "4242"
    assert "iOS Engineer" in body["text"]
    # Plain text: no parse_mode, so job titles with markdown-ish chars never break rendering.
    assert "parse_mode" not in body


async def test_long_digest_splits_into_multiple_bounded_posts() -> None:
    sent_texts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent_texts.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    notifier = TelegramNotifier(client, bot_token="T", chat_id="1")

    await notifier.send(_digest(*[f"Role {i} " + "x" * 200 for i in range(60)]))

    assert len(sent_texts) > 1
    assert all(len(text) <= TELEGRAM_MAX_CHARS for text in sent_texts)


async def test_raises_when_telegram_rejects_the_send() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "chat not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    notifier = TelegramNotifier(client, bot_token="T", chat_id="bad")

    with pytest.raises(httpx.HTTPStatusError):
        await notifier.send(_digest("iOS Engineer"))


async def test_stdout_notifier_prints_the_digest(capsys: pytest.CaptureFixture[str]) -> None:
    await StdoutNotifier().send(_digest("iOS Engineer"))

    out = capsys.readouterr().out
    assert "Senior iOS" in out
    assert "iOS Engineer" in out
