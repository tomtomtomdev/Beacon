"""Hacker News "Who is hiring?" as a company-less JobSource.

Uses the official Firebase API (github.com/HackerNews/API): the ``whoishiring`` user's
latest submission whose title says "Who is hiring?" is the current thread; its top-level
``kids`` are the postings. Each comment is one item fetch, so the thread's comment ids are
fetched with bounded concurrency and cached per thread — a re-poll only fetches unseen kids.

Deleted/dead comments, replies with no parseable header, and items the API can't return are
dropped. Parsing the header line is the pure domain concern (``parse_hn_posting``); the
company is read from the posting itself, so jobs carry ``company_name``.
"""

import asyncio
import logging
from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.hn import parse_hn_posting
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

_API = "https://hacker-news.firebaseio.com/v0"
_THREAD_TITLE = "who is hiring"
# The three monthly threads sit at the top of the user's submissions; scan a small window.
_MAX_SUBMISSIONS_SCANNED = 30


class HNAdapter:
    source_id = "hn"

    def __init__(self, fetcher: Fetcher, *, concurrency: int = 10) -> None:
        self._fetcher = fetcher
        self._concurrency = concurrency
        self._thread_id: str | None = None
        self._seen_kids: set[str] = set()

    async def fetch(self) -> list[RawPosting]:
        thread = await self._latest_hiring_thread()
        if thread is None:
            logger.info("hn_no_thread")
            return []

        thread_id = str(thread["id"])
        if thread_id != self._thread_id:  # new month → forget the previous thread's cache
            self._thread_id = thread_id
            self._seen_kids = set()

        kids = [str(kid) for kid in thread.get("kids") or []]
        unseen = [kid for kid in kids if kid not in self._seen_kids]
        results = await self._fetch_items(unseen)

        # Cache kids the API answered for (even a `null` for a purged item) so they are not
        # re-fetched; a kid whose fetch *raised* stays uncached and is retried next poll.
        self._seen_kids.update(kid for kid, _, ok in results if ok)
        postings = [item for _, item, ok in results if ok and item and _is_posting(item)]
        logger.info(
            "hn_poll thread=%s kids=%d unseen=%d postings=%d",
            thread_id,
            len(kids),
            len(unseen),
            len(postings),
        )
        return postings

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        text = str(raw.get("text") or "")
        posting = parse_hn_posting(text)
        if posting is None:
            raise ValueError(f"HN item {raw.get('id')!r} is not a parseable posting")

        description = normalize_description(text)
        item_id = str(raw["id"])
        country, city = parse_location(posting.location) if posting.location else (None, None)
        time = raw.get("time")  # epoch seconds, may be absent
        posted_at = datetime.fromtimestamp(time, tz=UTC) if time is not None else None
        return NormalizedJob(
            source_id=self.source_id,
            external_id=item_id,
            title=posting.role or posting.company,
            url=f"https://news.ycombinator.com/item?id={item_id}",
            description=description,
            location_raw=posting.location or "",
            country=country,
            city=city,
            posted_at=posted_at,
            content_hash=content_hash(description),
            company_name=posting.company,
        )

    async def _latest_hiring_thread(self) -> RawPosting | None:
        user = await self._fetcher.get_json(f"{_API}/user/whoishiring.json")
        submitted = [str(i) for i in (user.get("submitted") or [])][:_MAX_SUBMISSIONS_SCANNED]
        for item_id in submitted:
            item: RawPosting | None = await self._fetcher.get_json(f"{_API}/item/{item_id}.json")
            if item and _THREAD_TITLE in str(item.get("title") or "").casefold():
                return item
        return None

    async def _fetch_items(self, ids: list[str]) -> list[tuple[str, RawPosting | None, bool]]:
        """Fetch each comment id with bounded concurrency. Returns (id, item, ok) per kid;
        ok is False only when the fetch raised (so it can be retried), True for a `null`."""
        semaphore = asyncio.Semaphore(self._concurrency)

        async def fetch_one(item_id: str) -> tuple[str, RawPosting | None, bool]:
            async with semaphore:
                try:
                    item: RawPosting | None = await self._fetcher.get_json(
                        f"{_API}/item/{item_id}.json"
                    )
                    return item_id, item, True
                except Exception:
                    logger.exception("hn_item_failed id=%s", item_id)
                    return item_id, None, False

        return list(await asyncio.gather(*(fetch_one(item_id) for item_id in ids)))


def _is_posting(item: RawPosting) -> bool:
    if item.get("deleted") or item.get("dead"):
        return False
    text = item.get("text")
    return bool(text) and parse_hn_posting(str(text)) is not None
