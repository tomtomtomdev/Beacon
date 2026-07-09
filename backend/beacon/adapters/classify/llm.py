"""LLMClassifier — Anthropic Messages API fallback for the ambiguous residue the heuristic
leaves (empty category set). Implements the Classifier port with ONE JSON-only call per job.

Kept deliberately dumb: it fetches and parses, and raises on any reply it cannot read. The
heuristic-first gate, the monthly budget, and the fall-back-to-heuristic-on-failure policy
all live in the sibling TieredClassifier — this adapter is the pure "call the model" edge.

The Classifier port is synchronous, so this uses a sync httpx client. That is fine: the LLM
is a paying-customer API (no politeness/PoliteClient), and classification runs inside the
sequential per-posting ingest loop, so a blocking call stalls nothing that could progress.
"""

import json
import logging
from typing import Any

import httpx

from beacon.domain.classification import Category, Classification, Level
from beacon.domain.job import NormalizedJob

logger = logging.getLogger(__name__)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_MAX_TOKENS = 256
# Enough of the body to name an ambiguous role without paying for a whole JD in tokens.
_MAX_DESCRIPTION_CHARS = 2000

_CATEGORY_VALUES = {c.value for c in Category}

_PROMPT_TEMPLATE = (
    "Classify this software job posting. Respond with ONLY a JSON object — no prose, no "
    'markdown fences — in exactly this form: {{"categories": [...], "level": "..."}}.\n'
    "categories: zero or more of [{categories}]; use the ones the role actually is, and an "
    "empty list is correct when none apply.\n"
    "level: exactly one of [{levels}].\n\n"
    "Title: {title}\n"
    "Description: {description}"
)


class LLMClassifier:
    def __init__(self, client: httpx.Client, *, api_key: str, model: str) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model

    def classify(self, job: NormalizedJob) -> Classification:
        """One Anthropic call → Classification. Raises on a transport/HTTP error or a reply
        we cannot parse; the tiered classifier catches that and keeps the heuristic result."""
        prompt = _PROMPT_TEMPLATE.format(
            categories=", ".join(sorted(_CATEGORY_VALUES)),
            levels=", ".join(lvl.value for lvl in Level),
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


def _parse(text: str) -> Classification:
    """The model's JSON reply → Classification. Tolerant of surrounding prose or ```json
    fences (extract the outermost object) and of unknown enum values (dropped/defaulted);
    raises ValueError only when there is no readable JSON object at all."""
    obj = _extract_json_object(text)
    raw_categories = obj.get("categories", [])
    if not isinstance(raw_categories, list):
        raise ValueError("LLM response 'categories' is not a list")
    categories = frozenset(Category(value) for value in raw_categories if value in _CATEGORY_VALUES)
    return Classification(categories=categories, level=_to_level(obj.get("level")))


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


def _to_level(value: Any) -> Level:
    """A valid level string → that Level; anything else → UNSPECIFIED (an honest default,
    so a junk level never fails an otherwise-good classification)."""
    if isinstance(value, str):
        try:
            return Level(value)
        except ValueError:
            return Level.UNSPECIFIED
    return Level.UNSPECIFIED
