"""TieredClassifier — heuristic first, LLM only on the ambiguous residue, cost-capped.

Implements the Classifier port by composing two Classifiers, so the whole pipeline keeps
taking a single `classifier` and never learns the LLM exists. The LLM is a strict upgrader:
it is consulted only when the heuristic left no category (`Classification.is_ambiguous`) and
the monthly budget allows, and ANY failure (bad JSON, HTTP error, timeout) degrades silently
back to the heuristic result — the LLM is never a dependency the pipeline can die on.
"""

import logging

from beacon.application.ports import Classifier, LLMBudget
from beacon.domain.classification import Classification, Level
from beacon.domain.job import NormalizedJob

logger = logging.getLogger(__name__)


class TieredClassifier:
    def __init__(self, heuristic: Classifier, llm: Classifier | None, budget: LLMBudget) -> None:
        self._heuristic = heuristic
        self._llm = llm
        self._budget = budget

    def classify(self, job: NormalizedJob) -> Classification:
        result = self._heuristic.classify(job)
        if not result.is_ambiguous or self._llm is None:
            return result
        if not self._budget.try_reserve():
            logger.info(
                "llm_skip reason=budget_exhausted source=%s external_id=%s",
                job.source_id,
                job.external_id,
            )
            return result
        try:
            upgraded = self._llm.classify(job)
        except Exception:
            logger.warning(
                "llm_classify_failed source=%s external_id=%s (kept heuristic result)",
                job.source_id,
                job.external_id,
                exc_info=True,
            )
            return result
        # The LLM fills the empty categories; don't let it erase a level the heuristic was
        # sure of (a title token like "Senior") by returning UNSPECIFIED.
        level = upgraded.level if upgraded.level is not Level.UNSPECIFIED else result.level
        return Classification(categories=upgraded.categories, level=level)
