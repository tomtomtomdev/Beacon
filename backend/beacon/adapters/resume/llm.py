"""LLMMatcher — the Anthropic Messages API deep-match (§11 Tier 2). Implements the Matcher port
with ONE JSON-only call per job: it hands the model the resume text and the posting's own text
(plus Beacon's sponsorship signal) and parses the reply into a MatchRationale.

Kept deliberately dumb, like the LLMClassifier: it builds the prompt, calls, and raises on any
reply it cannot read. The on-demand trigger, the shared monthly budget, the cache, and the
fall-back-to-heuristic-on-failure policy all live in the deep_match_job use case — the LLM is an
upgrader, never a dependency the drawer can die on.

Synchronous, exactly like the LLMClassifier: the /jobs/{id}/match handler is a sync `def` (so it
runs in the threadpool alongside the sync sqlite repos, avoiding cross-thread connection use), so
a blocking client stalls nothing that could otherwise progress.
"""

import json
import logging
from typing import Any

import httpx

from beacon.domain.resume import DeepMatchJob, MatchRationale, Resume

logger = logging.getLogger(__name__)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_MAX_TOKENS = 512
# Enough resume/JD to reason about fit without paying for whole documents in tokens.
_MAX_RESUME_CHARS = 4000
_MAX_DESCRIPTION_CHARS = 4000

_PROMPT_TEMPLATE = (
    "Assess how well this candidate's resume fits this job posting. Respond with ONLY a JSON "
    "object — no prose, no markdown fences — in exactly this form: "
    '{{"summary": "...", "strengths": ["..."], "gaps": ["..."], "verdict": "...", '
    '"sponsor_note": "..."}}.\n'
    "summary: one or two sentences on the overall fit.\n"
    "strengths: concrete reasons this candidate fits (skills/experience they have).\n"
    "gaps: concrete things the posting wants that the resume does not show.\n"
    "verdict: a single short 'worth applying?' line.\n"
    "sponsor_note: one line on the visa-sponsorship fit, given the tier and country below.\n\n"
    "The heuristic pre-screen already found matched skills [{matched}] and missing skills "
    "[{missing}]; use them but do not merely repeat them.\n"
    "Sponsorship tier: {sponsor_tier}. Job country: {country}.\n\n"
    "=== RESUME ===\n{resume}\n\n"
    "=== JOB: {title} ===\n{description}"
)


class LLMMatcher:
    def __init__(self, client: httpx.Client, *, api_key: str, model: str) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model

    def deep_match(self, resume: Resume, job: DeepMatchJob) -> MatchRationale:
        """One Anthropic call → MatchRationale. Raises on a transport/HTTP error or a reply we
        cannot parse; the use case catches that and keeps the heuristic-only result."""
        prompt = _PROMPT_TEMPLATE.format(
            matched=", ".join(sorted(job.heuristic.matched_skills)),
            missing=", ".join(sorted(job.heuristic.missing_skills)),
            sponsor_tier=job.sponsor_tier.value,
            country=job.country or "unspecified",
            resume=resume.source_text[:_MAX_RESUME_CHARS],
            title=job.title,
            description=job.description[:_MAX_DESCRIPTION_CHARS],
        )
        response = self._client.post(
            _API_URL,
            headers={"x-api-key": self._api_key, "anthropic-version": _API_VERSION},
            json={
                "model": self._model,
                "max_tokens": _MAX_TOKENS,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        return _parse(_text_of(response.json()))


def _text_of(payload: Any) -> str:
    """The assistant's text out of a Messages API response, or ValueError if the envelope
    isn't the documented {content: [{type: 'text', text: ...}]} shape."""
    if isinstance(payload, dict):
        for block in payload.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text
    raise ValueError("unexpected Anthropic response shape: no text block")


def _parse(text: str) -> MatchRationale:
    """The model's JSON reply → MatchRationale. Tolerant of surrounding prose or ```json fences
    (extract the outermost object) and of missing fields (defaulted); raises ValueError only when
    there is no readable JSON object at all."""
    obj = _extract_json_object(text)
    return MatchRationale(
        summary=_as_str(obj.get("summary")),
        strengths=_as_str_tuple(obj.get("strengths")),
        gaps=_as_str_tuple(obj.get("gaps")),
        verdict=_as_str(obj.get("verdict")),
        sponsor_note=_as_str(obj.get("sponsor_note")),
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in LLM response")
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response is not valid JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("LLM response JSON is not an object")
    return obj


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
