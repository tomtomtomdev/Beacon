"""The Muse public jobs API as a company-less JobSource (SPEC §5.2).

100,845 software-engineering postings across 5,043 pages, no key. Polled category-scoped
rather than as a firehose, paged to a cap, deduped by the board's numeric id — hitting the
cap LOGS it (`themuse_page_cap`) so a partial sweep never reads as a complete one.

Two of the board's own fields beat our inference, and that precedence is the point of this
adapter (SPEC §5.4):

* `levels[]` — the employer's own seniority, so it wins over the title regex. Only the
  values with a real Beacon equivalent are carried: "Mid Level" and "Management" have none,
  and answering UNSPECIFIED for them would *override* a title that does name a level.
* `locations[]` — real places, except "Flexible / Remote", which is a filter value the board
  mixes into the list. A posting whose only location is that sentinel is country-less; we do
  not invent a country for a remote ad.
"""

import logging
from datetime import datetime
from typing import Any

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.classification import Level
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

_JOBS_API = "https://www.themuse.com/api/public/jobs"
_CATEGORY = "Software Engineering"
_MAX_PAGES = 3  # 60 newest postings per poll; the rest arrive on later polls

# The board's level vocabulary, as data. "Mid Level" and "Management" are deliberately
# absent — see the module docstring.
LEVELS: dict[str, Level] = {
    "Internship": Level.INTERN,
    "Entry Level": Level.JUNIOR,
    "Senior Level": Level.SENIOR,
}
# Not a place: the board's own "anywhere" filter value, mixed in among real locations.
_REMOTE_SENTINEL = "Flexible / Remote"


class TheMuseAdapter:
    source_id = "themuse"

    def __init__(
        self, fetcher: Fetcher, *, category: str = _CATEGORY, max_pages: int = _MAX_PAGES
    ) -> None:
        self._fetcher = fetcher
        self._category = category
        self._max_pages = max_pages

    async def fetch(self) -> list[RawPosting]:
        by_id: dict[str, RawPosting] = {}
        page_count: int | None = None
        for page in range(1, self._max_pages + 1):
            data = await self._fetcher.get_json(
                _JOBS_API, params={"page": str(page), "category": self._category}
            )
            for raw in data.get("results") or []:
                by_id.setdefault(str(raw["id"]), raw)
            page_count = data.get("page_count")
            if page_count is not None and page >= page_count:
                return list(by_id.values())
        logger.info(
            "themuse_page_cap category=%s fetched=%d pages=%d of=%s",
            self._category,
            len(by_id),
            self._max_pages,
            page_count,
        )
        return list(by_id.values())

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        places = [str(place["name"]) for place in (raw.get("locations") or [])]
        country, city = self._place(places)
        description = normalize_description(str(raw.get("contents") or ""))
        published = raw.get("publication_date")
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["name"]),
            url=str((raw.get("refs") or {}).get("landing_page") or ""),
            description=description,
            location_raw=", ".join(places),
            country=country,
            city=city,
            posted_at=self._published_at(published),
            content_hash=content_hash(description),
            company_name=str((raw.get("company") or {}).get("name") or "") or None,
            source_level=self._level(raw),
        )

    @staticmethod
    def _place(places: list[str]) -> tuple[str | None, str | None]:
        """The first real location; the remote sentinel names no country to report."""
        real = [place for place in places if place != _REMOTE_SENTINEL]
        return parse_location(real[0]) if real else (None, None)

    @staticmethod
    def _level(raw: RawPosting) -> Level | None:
        for level in raw.get("levels") or []:
            mapped = LEVELS.get(str(level.get("name")))
            if mapped is not None:
                return mapped
        return None

    @staticmethod
    def _published_at(published: Any) -> datetime | None:
        # ISO-8601 with a literal Z, which fromisoformat only accepts from 3.11 on.
        return datetime.fromisoformat(str(published)) if published else None
