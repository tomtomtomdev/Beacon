"""LLMClassifier — the Anthropic Messages API fallback, tested against recorded response
shapes via httpx.MockTransport (never a live call). It makes ONE JSON-only call and parses
the reply; the heuristic-first gate, budget and error fallback live in the tiered classifier.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.classify.llm import LLMClassifier
from beacon.domain.classification import Category, Level
from beacon.domain.job import NormalizedJob


def _job(title: str = "Software Engineer", description: str = "Build things.") -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse:test",
        external_id="1",
        title=title,
        url="https://example.test/1",
        description=description,
        location_raw="Remote",
        country=None,
        city=None,
        posted_at=datetime(2026, 7, 1, tzinfo=UTC),
        content_hash="hash",
    )


def _classifier(handler: Callable[[httpx.Request], httpx.Response]) -> LLMClassifier:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMClassifier(client, api_key="sk-test-KEY", model="claude-haiku-4-5-20251001")


def _responder(
    load_fixture: Callable[[str], Any], relative_path: str
) -> Callable[[httpx.Request], httpx.Response]:
    body = cast(dict[str, Any], load_fixture(relative_path))
    return lambda _request: httpx.Response(200, json=body)


def test_classify_posts_a_json_only_prompt_to_the_messages_api(
    load_fixture: Callable[[str], Any],
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=load_fixture("anthropic/classification_valid.json"))

    _classifier(handler).classify(_job(title="Platform Engineer", description="Own Kafka."))

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "sk-test-KEY"
    assert request.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(request.content)
    assert body["model"] == "claude-haiku-4-5-20251001"
    prompt = body["messages"][0]["content"]
    # JSON-only instruction, the enum options, and the job's own text all reach the model.
    assert "JSON" in prompt
    assert "backend" in prompt and "senior" in prompt
    assert "Platform Engineer" in prompt and "Own Kafka." in prompt


def test_classify_parses_categories_and_level(load_fixture: Callable[[str], Any]) -> None:
    result = _classifier(_responder(load_fixture, "anthropic/classification_valid.json")).classify(
        _job()
    )

    assert result.categories == frozenset({Category.BACKEND, Category.AI_ML})
    assert result.level == Level.SENIOR


def test_classify_tolerates_markdown_fenced_json(load_fixture: Callable[[str], Any]) -> None:
    result = _classifier(_responder(load_fixture, "anthropic/classification_fenced.json")).classify(
        _job()
    )

    assert result.categories == frozenset({Category.IOS})
    assert result.level == Level.STAFF


def test_classify_drops_category_values_outside_the_taxonomy(
    load_fixture: Callable[[str], Any],
) -> None:
    result = _classifier(
        _responder(load_fixture, "anthropic/classification_unknown_category.json")
    ).classify(_job())

    # "devrel" is not a Category — ignored, not fatal; the known value survives.
    assert result.categories == frozenset({Category.FRONTEND})
    assert result.level == Level.PRINCIPAL


def test_classify_raises_when_the_reply_is_not_json(load_fixture: Callable[[str], Any]) -> None:
    classifier = _classifier(_responder(load_fixture, "anthropic/refusal_prose.json"))

    with pytest.raises(ValueError, match="JSON"):
        classifier.classify(_job())


def test_classify_raises_on_an_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error"}})

    with pytest.raises(httpx.HTTPStatusError):
        _classifier(handler).classify(_job())
