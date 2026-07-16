"""LLMMatcher — the Anthropic Messages API deep-match (§11 Tier 2), tested against recorded
response shapes via httpx.MockTransport (never a live call). It makes ONE JSON-only call and
parses the reply into a MatchRationale; the budget gate, cache and fall-back-to-heuristic all
live in the deep_match_job use case — this adapter is the pure 'call the model' edge."""

import json
from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest

from beacon.adapters.resume.llm import LLMMatcher
from beacon.domain.classification import Category, Level
from beacon.domain.resume import DeepMatchJob, MatchScore, Resume, ResumeProfile
from beacon.domain.sponsorship import SponsorTier


def _resume() -> Resume:
    profile = ResumeProfile(
        skills=frozenset({"swift", "swiftui"}),
        categories=frozenset({Category.IOS}),
        level=Level.SENIOR,
        years=8,
        target_countries=frozenset({"SE"}),
    )
    return Resume(
        id=1,
        label="CV",
        source_text="Senior iOS Engineer, 8 years of Swift and SwiftUI.",
        profile=profile,
        resume_hash="resume-abc",
        active=True,
        created_at=None,
    )


def _job() -> DeepMatchJob:
    return DeepMatchJob(
        title="Senior iOS Engineer",
        description="Build the iOS app with Swift and SwiftUI. Kotlin a plus.",
        country="SE",
        sponsor_tier=SponsorTier.REGISTRY_INFERRED,
        heuristic=MatchScore(
            overall=90,
            skills_score=100,
            level_score=100,
            sponsor_score=38,
            matched_skills=frozenset({"swift", "swiftui"}),
            missing_skills=frozenset({"kotlin"}),
        ),
    )


def _matcher(handler: Callable[[httpx.Request], httpx.Response]) -> LLMMatcher:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMMatcher(client, api_key="sk-test-KEY", model="claude-haiku-4-5-20251001")


def _responder(
    load_fixture: Callable[[str], Any], relative_path: str
) -> Callable[[httpx.Request], httpx.Response]:
    body = cast(dict[str, Any], load_fixture(relative_path))
    return lambda _request: httpx.Response(200, json=body)


def test_deep_match_posts_a_json_only_prompt_with_resume_and_job(
    load_fixture: Callable[[str], Any],
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=load_fixture("anthropic/match_valid.json"))

    _matcher(handler).deep_match(_resume(), _job())

    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "sk-test-KEY"
    assert request.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(request.content)
    assert body["model"] == "claude-haiku-4-5-20251001"
    prompt = body["messages"][0]["content"]
    # JSON-only instruction, the resume text, and the job's own text all reach the model.
    assert "JSON" in prompt
    assert "Swift" in prompt and "Senior iOS Engineer" in prompt
    # Beacon's edge: the sponsorship tier is in the prompt so the rationale can speak to it.
    assert "registry_inferred" in prompt


def test_deep_match_parses_the_rationale(load_fixture: Callable[[str], Any]) -> None:
    rationale = _matcher(_responder(load_fixture, "anthropic/match_valid.json")).deep_match(
        _resume(), _job()
    )

    assert rationale.summary.startswith("Strong iOS fit")
    assert rationale.strengths == ("8 years of Swift and SwiftUI", "Ships production iOS apps")
    assert rationale.gaps == ("No Kotlin exposure", "Backend depth is light")
    assert rationale.verdict == "Worth applying."
    assert "target country" in rationale.sponsor_note


def test_deep_match_tolerates_markdown_fenced_json(load_fixture: Callable[[str], Any]) -> None:
    rationale = _matcher(_responder(load_fixture, "anthropic/match_fenced.json")).deep_match(
        _resume(), _job()
    )

    assert rationale.verdict.startswith("Stretch")
    assert rationale.strengths == ("Relevant category",)


def test_deep_match_raises_when_the_reply_is_not_json(load_fixture: Callable[[str], Any]) -> None:
    matcher = _matcher(_responder(load_fixture, "anthropic/match_refusal.json"))

    with pytest.raises(ValueError, match="JSON"):
        matcher.deep_match(_resume(), _job())


def test_deep_match_raises_on_an_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error"}})

    with pytest.raises(httpx.HTTPStatusError):
        _matcher(handler).deep_match(_resume(), _job())
