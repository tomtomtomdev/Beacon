"""Manual LLM-fallback spot-check — the slice-9 acceptance gate.

Fetches real postings from live Greenhouse boards, finds the ambiguous residue the heuristic
leaves (empty category set — the Research Engineer / Data Scientist / generic-SWE tail from
the slice-3 spot-check), then sends only that residue to the real LLMClassifier and prints
heuristic-before vs LLM-after so the improvement can be eyeballed. Live network + a real
Anthropic call by design (manual acceptance only, never the suite):

    cd backend && BEACON_ANTHROPIC_API_KEY=sk-ant-... uv run python scripts/spot_check_llm.py [--limit 15]

Acceptance (PLAN slice 9): >= 15 previously-unspecified rows improved, call count under budget.
"""

import argparse
import asyncio
import re

import httpx

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.adapters.classify.llm import LLMClassifier
from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.config import Settings
from beacon.domain.classification import format_categories
from beacon.domain.job import NormalizedJob

SLUGS = ("anthropic", "adyen", "agoda", "tines")
_ENGINEERING_TITLE = re.compile(r"engineer|developer|scientist|programmer", re.IGNORECASE)


async def _ambiguous_residue(client: httpx.AsyncClient) -> list[NormalizedJob]:
    """Real engineering-titled postings the heuristic leaves with no category."""
    heuristic = HeuristicClassifier()
    residue: list[NormalizedJob] = []
    for slug in SLUGS:
        adapter = GreenhouseAdapter(slug, PoliteClient(client))
        for raw in await adapter.fetch():
            job = adapter.normalize(raw)
            if _ENGINEERING_TITLE.search(job.title) and heuristic.classify(job).is_ambiguous:
                residue.append(job)
    return residue


async def _run(limit: int) -> int:
    settings = Settings.from_env()
    if settings.anthropic_api_key is None:
        print("set BEACON_ANTHROPIC_API_KEY to run the live LLM spot-check")
        return 1

    async with httpx.AsyncClient(timeout=15.0) as client:
        residue = await _ambiguous_residue(client)

    # Stride so the sample spans boards/alphabet rather than clustering on one board's head.
    step = max(1, len(residue) // limit) if residue else 1
    sample = residue[::step][:limit]

    improved = calls = errors = 0
    with httpx.Client(timeout=30.0) as llm_client:
        llm = LLMClassifier(
            llm_client,
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
        )
        print(f"{'#':>2}  {'LLM categories':22} {'Level':12} Title")
        print("-" * 96)
        for i, job in enumerate(sample, 1):
            try:
                result = llm.classify(job)
                calls += 1
            except Exception as exc:  # spot-check must not die on one bad reply
                errors += 1
                print(f"{i:>2}  {'ERROR':22} {'—':12} {job.title[:44]}  ({type(exc).__name__})")
                continue
            if result.categories:
                improved += 1
            print(
                f"{i:>2}  {format_categories(result.categories) or '—':22}"
                f" {result.level.value:12} {job.title[:44]}"
            )
    print("-" * 96)
    print(
        f"residue={len(residue)} sampled={len(sample)}"
        f" llm_calls={calls} improved={improved} errors={errors}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Live LLM-fallback spot-check over the residue.")
    parser.add_argument("--limit", type=int, default=15, help="residue postings to send (def 15)")
    args = parser.parse_args()
    return asyncio.run(_run(args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
