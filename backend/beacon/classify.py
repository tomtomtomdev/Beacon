"""CLI composition root: python -m beacon.classify [--upgrade-residue].

Wiring only. Default mode classifies every job never classified (categories IS NULL), e.g.
rows ingested before the classifier existed; --upgrade-residue instead re-runs the LLM over
the empty-category residue (categories = '') to resolve titles the heuristic couldn't.

The classifier is heuristic-only until an Anthropic key is set, else a budget-gated tiered
classifier — so a plain backfill works fully offline, and the LLM upgrade needs the key.
"""

import argparse
import logging

import httpx

from beacon.adapters.classify.factory import make_classifier
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.llm_budget import SqliteLLMBudget
from beacon.application.backfill import (
    backfill_classifications,
    upgrade_ambiguous_classifications,
)
from beacon.config import Settings


def _run(settings: Settings, *, upgrade_residue: bool) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)

    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    budget = SqliteLLMBudget(conn, cap=settings.llm_monthly_budget)
    jobs = SqliteJobRepo(conn)

    with httpx.Client(timeout=30.0) as client:
        classifier = make_classifier(
            client, api_key=api_key, model=settings.llm_model, budget=budget
        )
        if upgrade_residue:
            improved = upgrade_ambiguous_classifications(jobs, classifier)
            print(f"upgrade improved={improved} llm_calls_this_month={budget.calls_this_month()}")
        else:
            classified = backfill_classifications(jobs, classifier)
            print(
                f"backfill classified={classified} llm_calls_this_month={budget.calls_this_month()}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify jobs (heuristic + optional LLM).")
    parser.add_argument(
        "--upgrade-residue",
        action="store_true",
        help="re-run the LLM over empty-category rows instead of classifying NULL rows",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return _run(Settings.from_env(), upgrade_residue=args.upgrade_residue)


if __name__ == "__main__":
    raise SystemExit(main())
