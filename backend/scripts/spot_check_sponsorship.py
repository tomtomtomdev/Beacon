"""Manual sponsorship-text spot-check — the slice-6 acceptance gate.

Fetches real postings from a spread of live boards, runs each description through the
real adapter + domain detect_sponsorship, and prints the tier + matched evidence
sentence for every posting that carries an explicit signal. It also flags "MISS?"
candidates: postings whose text mentions visa/sponsor/relocation/right-to-work language
but that the detector left silent — those are the rows to eyeball for new phrase-table
entries. Live network by design (manual acceptance only, never the suite):

    cd backend && uv run python scripts/spot_check_sponsorship.py [--limit 40]

Acceptance (PLAN slice 6): tier + evidence correct >= 90% on postings containing
sponsorship language. Log every miss as a new phrase row in domain/sponsorship.py and a
parametrized row in tests/unit/test_sponsorship.py (append, never delete).
"""

import argparse
import asyncio
import re
from collections import Counter

import httpx

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.greenhouse import GreenhouseAdapter
from beacon.domain.sponsorship import _SENTENCE_SPLIT, detect_sponsorship

# Verified-live Greenhouse slugs (slice-1 task 0), spanning EU + US employers where
# work-authorization / relocation language actually shows up in postings.
SLUGS = ("anthropic", "adyen", "agoda", "tines")

# Words that hint a posting *talks about* sponsorship/authorization — used only to spot
# detector misses (a hit here with no tier is a "MISS?" candidate for the phrase table).
_HINT = re.compile(r"visa|sponsor|relocat|right to work|work authori|green card", re.IGNORECASE)


async def _rows(slug: str, client: httpx.AsyncClient) -> list[tuple[str, str, str, str]]:
    adapter = GreenhouseAdapter(slug, PoliteClient(client))
    rows: list[tuple[str, str, str, str]] = []
    for raw in await adapter.fetch():
        job = adapter.normalize(raw)
        signal = detect_sponsorship(job.description)
        if signal is not None:
            rows.append((slug, job.title, signal.tier.value, signal.evidence or ""))
        elif _HINT.search(job.description):
            sentences = _SENTENCE_SPLIT.split(job.description)
            hint = next((s for s in sentences if _HINT.search(s)), "")
            rows.append((slug, job.title, "MISS?", " ".join(hint.split())[:88]))
    return rows


async def _run(limit: int) -> int:
    async with httpx.AsyncClient(timeout=15.0) as client:
        found = [row for slug in SLUGS for row in await _rows(slug, client)]
    sample = found[:limit]

    tiers: Counter[str] = Counter()
    print(f"{'#':>2}  {'Company':10} {'Tier':16} Title / Evidence")
    print("-" * 104)
    for i, (slug, title, tier, evidence) in enumerate(sample, 1):
        tiers[tier] += 1
        print(f"{i:>2}  {slug:10} {tier:16} {title[:44]}")
        print(f"{'':>2}  {'':10} {'':16} └ {evidence[:80]}")
    print("-" * 104)
    print(f"sampled={len(sample)}  tiers={dict(tiers)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live sponsorship-text spot-check over Greenhouse boards."
    )
    parser.add_argument("--limit", type=int, default=40, help="postings to show (default 40)")
    args = parser.parse_args()
    return asyncio.run(_run(args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
