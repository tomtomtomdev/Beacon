"""Classifier selection — the one place that decides heuristic-only vs heuristic+LLM.

Mirrors adapters/notify/factory.make_notifier: without an Anthropic API key it returns the
bare HeuristicClassifier, so ingest and backfill work fully unconfigured; with a key it wraps
heuristic + LLM in a budget-gated TieredClassifier. Either way the caller gets one Classifier.
"""

import httpx

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.classify.llm import LLMClassifier
from beacon.adapters.classify.tiered import TieredClassifier
from beacon.application.ports import Classifier, LLMBudget


def make_classifier(
    client: httpx.Client,
    *,
    api_key: str | None,
    model: str,
    budget: LLMBudget,
) -> Classifier:
    heuristic = HeuristicClassifier()
    if not api_key:
        return heuristic
    llm = LLMClassifier(client, api_key=api_key, model=model)
    return TieredClassifier(heuristic, llm, budget)
