"""Manual HN Who-is-hiring spot-check — the slice-7 acceptance gate.

Hits the live Firebase API, finds the current "Who is hiring?" thread, samples its
top-level comments through the real HNAdapter parse + normalize, and prints one line
per parsed posting so the junk rate can be eyeballed. Live network by design (manual
acceptance only, never the suite):

    cd backend && uv run python scripts/spot_check_hn.py [--limit 80]

Acceptance (PLAN slice 7): the current month's thread ingests and obvious junk is rare.
Rows tagged [no-role] parsed a company + location but no role from the header (roles
live in the body) — expected, not junk. Genuine junk is a non-company first field.
"""

import argparse
import asyncio
from typing import Any

import httpx

from beacon.adapters.http.polite import PoliteClient
from beacon.adapters.sources.hn import HNAdapter
from beacon.domain.hn import parse_hn_posting

_API = "https://hacker-news.firebaseio.com/v0"
_THREAD_TITLE = "who is hiring"


async def _latest_thread(fetcher: PoliteClient) -> dict[str, Any] | None:
    user: dict[str, Any] = await fetcher.get_json(f"{_API}/user/whoishiring.json")
    for submission_id in [str(i) for i in user.get("submitted") or []][:30]:
        item: dict[str, Any] | None = await fetcher.get_json(f"{_API}/item/{submission_id}.json")
        if item and _THREAD_TITLE in str(item.get("title") or "").casefold():
            return item
    return None


async def _run(limit: int) -> int:
    # HN's Firebase API is a read-only CDN that tolerates bursts; skip the 1 rps throttle.
    async with httpx.AsyncClient(timeout=15.0) as client:
        fetcher = PoliteClient(client, min_interval=0.0)
        adapter = HNAdapter(fetcher)

        thread = await _latest_thread(fetcher)
        if thread is None:
            print("no 'Who is hiring?' thread found in the latest submissions")
            return 1

        kids = [str(k) for k in thread.get("kids") or []]
        sample = kids[:limit]
        print(
            f"thread={thread['id']} title={thread.get('title')!r} kids={len(kids)} sample={len(sample)}"
        )

        items: list[dict[str, Any] | None] = list(
            await asyncio.gather(*(fetcher.get_json(f"{_API}/item/{k}.json") for k in sample))
        )

        parsed = skipped = no_role = 0
        for item in items:
            if not item or item.get("deleted") or item.get("dead") or not item.get("text"):
                skipped += 1
                continue
            if parse_hn_posting(str(item["text"])) is None:
                skipped += 1
                continue
            job = adapter.normalize(item)
            parsed += 1
            tag = "  [no-role]" if job.title == job.company_name else ""
            no_role += 1 if tag else 0
            print(
                f"  {job.company_name} | {job.title} | {job.location_raw or '—'} | {job.country or '—'}{tag}"
            )

        print(
            f"\nsampled={len(sample)} parsed_postings={parsed} skipped={skipped} no_role={no_role}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Spot-check HN Who-is-hiring parsing.")
    parser.add_argument("--limit", type=int, default=80, help="top-level comments to sample")
    return asyncio.run(_run(parser.parse_args().limit))


if __name__ == "__main__":
    raise SystemExit(main())
