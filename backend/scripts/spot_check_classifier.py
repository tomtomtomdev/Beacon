"""Manual classifier spot-check — the slice-3 acceptance gate.

Fetches real postings from a spread of live Greenhouse boards, runs them through the
real GreenhouseAdapter + HeuristicClassifier, and prints category/level per posting so
they can be eyeballed. Live network by design (manual acceptance only, never the suite):

    cd backend && uv run python scripts/spot_check_classifier.py [--limit 30]

Acceptance (PLAN slice 3): category correct >= 90%, level >= 80%. Log every miss as a
new parametrized row in tests/unit/test_classifier.py (append, never delete).
"""

import argparse
import asyncio
import re
from collections import Counter

import httpx

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.domain.classification import format_categories

# Verified-live slugs (slice-1 task 0) chosen for category spread: AI/ML + backend + a
# large multi-discipline travel-tech board that carries mobile/frontend roles.
SLUGS = ("anthropic", "adyen", "agoda", "tines")

# Titles that name a hands-on technical role — where a category SHOULD be detectable.
# --eng-only strides through just these so the sample stresses the classifier's real job
# rather than the sea of sales/ops postings (which correctly classify to no category).
_ENGINEERING_TITLE = re.compile(r"engineer|developer|scientist|programmer", re.IGNORECASE)


async def _postings(slug: str, client: httpx.AsyncClient) -> list[tuple[str, str, str, str]]:
    adapter = GreenhouseAdapter(slug, PoliteClient(client))
    classifier = HeuristicClassifier()
    rows: list[tuple[str, str, str, str]] = []
    for raw in await adapter.fetch():
        job = adapter.normalize(raw)
        result = classifier.classify(job)
        rows.append(
            (slug, job.title, format_categories(result.categories) or "—", result.level.value)
        )
    return rows


async def _run(limit: int, eng_only: bool) -> int:
    async with httpx.AsyncClient(timeout=15.0) as client:
        per_board = [await _postings(slug, client) for slug in SLUGS]

    if eng_only:
        per_board = [
            [row for row in board if _ENGINEERING_TITLE.search(row[1])] for board in per_board
        ]

    # Stride evenly through each board's list so the sample spans the alphabet
    # (roles sit mid/late) instead of clustering on the "Account*" head.
    quota = -(-limit // len(SLUGS))  # ceil
    sample: list[tuple[str, str, str, str]] = []
    for board in per_board:
        if not board:
            continue
        step = max(1, len(board) // quota)
        sample.extend(board[::step][:quota])
    sample = sample[:limit]

    cats: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    print(f"{'#':>2}  {'Company':10} {'Categories':22} {'Level':12} Title")
    print("-" * 104)
    for i, (slug, title, categories, level) in enumerate(sample, 1):
        for category in categories.split(","):
            cats[category] += 1
        levels[level] += 1
        print(f"{i:>2}  {slug:10} {categories:22} {level:12} {title[:48]}")
    print("-" * 104)
    print(f"sampled={len(sample)}  categories={dict(cats)}  levels={dict(levels)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live classifier spot-check over Greenhouse boards."
    )
    parser.add_argument("--limit", type=int, default=30, help="postings to sample (default 30)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="sample all roles (default: only engineering-titled roles)",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.limit, eng_only=not args.all))


if __name__ == "__main__":
    raise SystemExit(main())
