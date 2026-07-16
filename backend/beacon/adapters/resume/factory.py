"""Matcher selection — the one place that decides heuristic-only vs heuristic+LLM deep-match.

Mirrors adapters/classify/factory.make_classifier: without an Anthropic API key it returns None,
so the deep_match_job use case degrades to the heuristic-only result and the drawer's Fit card
never gains a rationale. With a key it returns an LLMMatcher. Tier 2 is LLM-only — there is no
heuristic matcher — so None is the honest 'off' value (the use case handles it), same switch as
slice 9's LLM classifier.
"""

import httpx

from beacon.adapters.resume.llm import LLMMatcher
from beacon.application.ports import Matcher


def make_matcher(client: httpx.Client, *, api_key: str | None, model: str) -> Matcher | None:
    if not api_key:
        return None
    return LLMMatcher(client, api_key=api_key, model=model)
