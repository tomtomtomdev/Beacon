"""make_classifier wires the classifier stack: heuristic-only until an Anthropic API key is
present, tiered (heuristic + LLM, budget-gated) once it is — mirroring make_notifier's
"unconfigured falls back" shape, so ingest never depends on the LLM being set up."""

import httpx

from beacon.adapters.classify.factory import make_classifier
from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.classify.tiered import TieredClassifier


class _StubBudget:
    def try_reserve(self) -> bool:
        return True


def _client() -> httpx.Client:
    # A transport that would explode if used — the factory must not make a call to wire.
    return httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(500)))


def test_make_classifier_is_heuristic_only_without_an_api_key() -> None:
    classifier = make_classifier(_client(), api_key=None, model="m", budget=_StubBudget())

    assert isinstance(classifier, HeuristicClassifier)


def test_make_classifier_is_tiered_with_an_api_key() -> None:
    classifier = make_classifier(_client(), api_key="sk-ant-x", model="m", budget=_StubBudget())

    assert isinstance(classifier, TieredClassifier)
