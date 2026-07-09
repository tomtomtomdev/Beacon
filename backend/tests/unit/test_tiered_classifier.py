"""TieredClassifier: heuristic first, LLM only on the ambiguous residue, cost-capped, and
degrading to the heuristic on any LLM failure — the LLM is an upgrader, never a dependency.

Uses the REAL HeuristicClassifier (pure, deterministic) so 'confident' vs 'ambiguous' is
driven by the actual gate, plus a FakeLLMClassifier that never touches the network.
"""

from datetime import UTC, datetime

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.classify.tiered import TieredClassifier
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.job import NormalizedJob

# The heuristic reads categories from the title only: a keyword title is confident, a bare
# "Software Engineer" title leaves categories empty → ambiguous → eligible for the LLM.
CONFIDENT = "Senior iOS Engineer"
AMBIGUOUS = "Software Engineer"


def _job(title: str, description: str = "Build things.") -> NormalizedJob:
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


class FakeLLMClassifier:
    """Canned stand-in for the Anthropic classifier — records calls, never hits the network."""

    def __init__(self, result: Classification, *, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[str] = []

    def classify(self, job: NormalizedJob) -> Classification:
        self.calls.append(job.external_id)
        if self._error is not None:
            raise self._error
        return self._result


class FakeBudget:
    def __init__(self, *, allow: bool = True) -> None:
        self._allow = allow
        self.reserves = 0

    def try_reserve(self) -> bool:
        self.reserves += 1
        return self._allow


def test_confident_heuristic_result_never_calls_the_llm() -> None:
    llm = FakeLLMClassifier(Classification(frozenset({Category.AI_ML}), Level.LEAD))
    budget = FakeBudget()
    tiered = TieredClassifier(HeuristicClassifier(), llm, budget)

    result = tiered.classify(_job(CONFIDENT))

    assert llm.calls == []  # heuristic was confident (title named the role)
    assert budget.reserves == 0  # a confident result never even touches the budget
    assert result.categories == frozenset({Category.IOS})


def test_ambiguous_result_is_upgraded_by_one_llm_call() -> None:
    llm = FakeLLMClassifier(Classification(frozenset({Category.BACKEND}), Level.SENIOR))
    budget = FakeBudget()
    tiered = TieredClassifier(HeuristicClassifier(), llm, budget)

    result = tiered.classify(_job(AMBIGUOUS))

    assert llm.calls == ["1"]  # ambiguous residue → exactly one LLM call
    assert budget.reserves == 1
    assert result == Classification(frozenset({Category.BACKEND}), Level.SENIOR)


def test_llm_failure_falls_back_to_the_heuristic_result() -> None:
    llm = FakeLLMClassifier(
        Classification(frozenset({Category.BACKEND}), Level.SENIOR),
        error=ValueError("LLM response is not valid JSON"),
    )
    tiered = TieredClassifier(HeuristicClassifier(), llm, FakeBudget())

    result = tiered.classify(_job(AMBIGUOUS))

    assert llm.calls == ["1"]  # it was tried
    assert result == Classification(frozenset(), Level.UNSPECIFIED)  # heuristic result kept


def test_llm_upgrade_keeps_a_level_the_heuristic_was_sure_of() -> None:
    # "Senior Software Engineer": heuristic gives empty categories but a sure SENIOR level.
    # The LLM fills categories but returns an unspecified level — we must not lose SENIOR.
    llm = FakeLLMClassifier(Classification(frozenset({Category.BACKEND}), Level.UNSPECIFIED))
    tiered = TieredClassifier(HeuristicClassifier(), llm, FakeBudget())

    result = tiered.classify(_job("Senior Software Engineer"))

    assert result == Classification(frozenset({Category.BACKEND}), Level.SENIOR)


def test_llm_not_called_when_the_monthly_budget_is_exhausted() -> None:
    llm = FakeLLMClassifier(Classification(frozenset({Category.BACKEND}), Level.SENIOR))
    budget = FakeBudget(allow=False)
    tiered = TieredClassifier(HeuristicClassifier(), llm, budget)

    result = tiered.classify(_job(AMBIGUOUS))

    assert budget.reserves == 1  # the budget was consulted
    assert llm.calls == []  # ...and refused, so no call was made
    assert result == Classification(frozenset(), Level.UNSPECIFIED)  # heuristic residue stands


def test_no_llm_configured_is_pure_heuristic() -> None:
    budget = FakeBudget()
    tiered = TieredClassifier(HeuristicClassifier(), None, budget)

    result = tiered.classify(_job(AMBIGUOUS))

    assert budget.reserves == 0  # without an LLM the budget is never touched
    assert result == Classification(frozenset(), Level.UNSPECIFIED)
