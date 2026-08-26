"""NAV Norway's stillingsfeed as a company-less JobSource (SPEC §5.4) — the first source
behind authentication. Norway's official register and the NO twin of JobTech.

`GET pam-stilling-feed.nav.no/api/v1/feed` needs a bearer token, which lives on the HTTP
door keyed by host (see PoliteClient) — this adapter never holds a credential. Without a
token configured the adapter is simply not wired, exactly like the Telegram/LLM precedent.

Three properties of this feed shape everything below:

* It is a *continuous historical feed*, running from ~2019, so a poll must say where to
  start: `modified_since` becomes NAV's documented If-Modified-Since filter, and the walk
  follows `next_url` until `next_id` is null (the head) or the page cap is reached (logged).
* An INACTIVE item is returned with its title and employer **stripped to "..."**, so ACTIVE
  filtering is not an optimisation — an inactive row has nothing left to classify.
* A feed item carries no ad text: the description needs `GET /api/v1/feedentry/{uuid}`,
  whose payload is `ad_content` (the published docs still call it `json`). An entry that
  closed between the two calls comes back without `ad_content` at all and is dropped.

Because every ACTIVE ad would otherwise cost one detail call, titles are filtered against
the shared vocabulary first. Measured 2026-08-26: 8 pages / 8,000 items over five days held
4,711 ACTIVE ads, of which 48 had a tech-shaped title — spending ~4,700 polite calls per
poll to find them would be the firehose slice 13 already refused for keyword boards.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location
from beacon.domain.vocabulary import extract_categories

logger = logging.getLogger(__name__)

NAV_HOST = "pam-stilling-feed.nav.no"
_BASE = f"https://{NAV_HOST}"
_FEED = f"{_BASE}/api/v1/feed"
_ACTIVE = "ACTIVE"
# How far back a poll starts. An ad can never be active for more than 6 months, but a
# 4-hourly poll only needs the last few days to stay at the head of the feed.
_WINDOW_DAYS = 3
_MAX_PAGES = 4  # ~1,000 items per page; the rest of the window arrives on later polls


class NAVAdapter:
    source_id = "nav"

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        window_days: int = _WINDOW_DAYS,
        max_pages: int = _MAX_PAGES,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._fetcher = fetcher
        self._window = timedelta(days=window_days)
        self._max_pages = max_pages
        self._now = now

    async def fetch(self) -> list[RawPosting]:
        entries: list[RawPosting] = []
        for uuid in await self._candidate_uuids():
            entry = await self._entry(uuid)
            if entry is not None:
                entries.append(entry)
        return entries

    async def _candidate_uuids(self) -> list[str]:
        """The ACTIVE ads in the window whose title names a role family, newest walk first."""
        url: str | None = _FEED
        uuids: list[str] = []
        pinned = self._now() - self._window
        for page in range(self._max_pages):
            if url is None:
                return uuids
            data = await self._fetcher.get_json(url, modified_since=pinned if page == 0 else None)
            uuids.extend(_wanted_uuids(data.get("items") or []))
            next_url = data.get("next_url")
            url = f"{_BASE}{next_url}" if next_url else None
        if url is not None:
            logger.info(
                "nav_page_cap pages=%d since=%s candidates=%d",
                self._max_pages,
                pinned.date(),
                len(uuids),
            )
        return uuids

    async def _entry(self, uuid: str) -> RawPosting | None:
        entry = await self._fetcher.get_json(f"{_BASE}/api/v1/feedentry/{uuid}")
        if not entry.get("ad_content"):
            # Closed between the feed page and this call: NAV strips the content, not just
            # the status. Nothing to ingest, and not a failure either.
            logger.info("nav_entry_without_content uuid=%s status=%s", uuid, entry.get("status"))
            return None
        content: RawPosting = entry
        return content

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        ad = raw["ad_content"]
        place = (ad.get("workLocations") or [{}])[0]
        location_raw = ", ".join(
            str(part) for part in (place.get("city"), place.get("country")) if part
        )
        country, _ = parse_location(str(place.get("country") or ""))
        description = normalize_description(str(ad.get("description") or ""))
        published = ad.get("published")
        employer = ad.get("employer") or {}
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["uuid"]),
            title=str(ad["title"]),
            url=str(ad.get("link") or ad.get("applicationUrl") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=str(place.get("city") or "") or None,
            # ISO-8601 with Norway's own offset ("+02:00") — converted, never truncated.
            posted_at=_as_utc(published),
            content_hash=content_hash(description),
            company_name=str(employer.get("name") or "") or None,
        )


def _wanted_uuids(items: list[RawPosting]) -> list[str]:
    return [
        str(item["_feed_entry"]["uuid"])
        for item in items
        if item["_feed_entry"].get("status") == _ACTIVE and extract_categories(str(item["title"]))
    ]


def _as_utc(published: Any) -> datetime | None:
    return datetime.fromisoformat(str(published)).astimezone(UTC) if published else None
