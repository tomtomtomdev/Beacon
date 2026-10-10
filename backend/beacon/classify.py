"""CLI composition root: python -m beacon.classify [--upgrade-residue | --reclassify CATEGORY].

Wiring only. Default mode classifies every job never classified (categories IS NULL), e.g.
rows ingested before the classifier existed; --upgrade-residue instead re-runs the classifier
over the empty-category residue (categories = ''): with a key, the LLM resolves titles the
heuristic couldn't; without one, the heuristic re-reads them with today's vocabulary — the
offline backfill after a vocabulary widening (slice 27b); --reclassify re-reads every row
stored with one category and rewrites those whose categories changed — the backfill after a
vocabulary split (slice 28b: `--reclassify backend` once infra left it).

The classifier is heuristic-only until an Anthropic key is set, else a budget-gated tiered
classifier — so a plain backfill works fully offline, and the LLM upgrade needs the key.
"""

import argparse

import httpx

from beacon.adapters.classify.factory import make_classifier
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.llm_budget import SqliteLLMBudget
from beacon.application.backfill import (
    backfill_classifications,
    reclassify_category,
    upgrade_ambiguous_classifications,
)
from beacon.config import Settings
from beacon.domain.classification import Category
from beacon.logging_setup import configure_cli_logging


def _run(settings: Settings, *, upgrade_residue: bool, reclassify: Category | None) -> int:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)

    api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    budget = SqliteLLMBudget(conn, cap=settings.llm_monthly_budget)
    jobs = SqliteJobRepo(conn)

    with httpx.Client(timeout=30.0) as client:
        classifier = make_classifier(
            client, api_key=api_key, model=settings.llm_model, budget=budget
        )
        if reclassify is not None:
            changed = reclassify_category(jobs, classifier, reclassify)
            print(
                f"reclassify category={reclassify} changed={changed} "
                f"llm_calls_this_month={budget.calls_this_month()}"
            )
        elif upgrade_residue:
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--upgrade-residue",
        action="store_true",
        help=(
            "re-run the classifier over empty-category rows instead of classifying NULL rows "
            "(heuristic-only without a key: applies a widened vocabulary offline)"
        ),
    )
    mode.add_argument(
        "--reclassify",
        type=Category,
        choices=list(Category),
        metavar="CATEGORY",
        help="re-run the classifier over rows stored with CATEGORY (the backfill after a split)",
    )
    args = parser.parse_args(argv)

    configure_cli_logging()
    return _run(
        Settings.from_env(), upgrade_residue=args.upgrade_residue, reclassify=args.reclassify
    )


if __name__ == "__main__":
    raise SystemExit(main())
