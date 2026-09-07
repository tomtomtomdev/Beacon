"""Himalayas search API as a company-less JobSource (SPEC §5.2).

Remote-only board, ~100k live postings, so it is polled through its *search* endpoint rather
than the firehose feed: one search per phrasing of the role families Beacon hunts, deduped by
guid. The queries are data — edit the tuple to widen coverage, never the walk below.
Attribution: postings keep their himalayas.app URL, which is the source link the board's
terms ask for.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

_SEARCH_API = "https://himalayas.app/jobs/api/search"
# The role families of SPEC §1, as the board's own search reads them — grouped by family,
# flat by design (the walk below takes one query at a time and dedupes by guid).
#
# iOS carries three phrasings because one was the cap: the board holds 565 live iOS postings
# and a single "ios engineer" poll reads 60 rows, 17 of which classify iOS (slice 14). The
# phrasings are the ones employers title with, and each is one a *title* can be matched on —
# "mobile engineer" is deliberately absent, because HeuristicClassifier reads the category
# from the title alone, so a row titled "Mobile Engineer" lands with no category however
# much iOS its body names, and the query would spend the polite budget on residue.
ROLE_QUERIES: tuple[str, ...] = (
    "ios engineer",
    "ios developer",
    "swift developer",
    "java backend engineer",
    "machine learning engineer",
)
_PAGE_SIZE = 20  # the search endpoint's maximum
_MAX_PAGES = 3  # 60 newest matches per query per poll; the rest arrive on later polls


class HimalayasAdapter:
    source_id = "himalayas"

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        queries: Sequence[str] = ROLE_QUERIES,
        page_size: int = _PAGE_SIZE,
        max_pages: int = _MAX_PAGES,
    ) -> None:
        self._fetcher = fetcher
        self._queries = tuple(queries)
        self._page_size = page_size
        self._max_pages = max_pages

    async def fetch(self) -> list[RawPosting]:
        by_guid: dict[str, RawPosting] = {}
        for query in self._queries:
            for raw in await self._search(query):
                by_guid.setdefault(str(raw["guid"]), raw)
        return list(by_guid.values())

    async def _search(self, query: str) -> list[RawPosting]:
        found: list[RawPosting] = []
        total: int | None = None
        for page in range(1, self._max_pages + 1):
            data = await self._fetcher.get_json(
                _SEARCH_API,
                params={"q": query, "limit": str(self._page_size), "page": str(page)},
            )
            jobs: list[RawPosting] = data["jobs"]
            total = data.get("totalCount")
            found.extend(jobs)
            if len(jobs) < self._page_size:
                return found
        # Paging stopped at the cap, not at the end of the results — say so rather than
        # letting a partial sweep look complete.
        logger.info("himalayas_page_cap query=%s fetched=%d total=%s", query, len(found), total)
        return found

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        restrictions = [str(part) for part in (raw.get("locationRestrictions") or [])]
        location_raw = ", ".join(restrictions)
        # An empty restriction list means work-from-anywhere: no country to report.
        country, city = parse_location(restrictions[0]) if restrictions else (None, None)
        description = normalize_description(str(raw.get("description") or ""))
        guid = str(raw["guid"])
        published = raw.get("pubDate")  # unix epoch seconds
        return NormalizedJob(
            source_id=self.source_id,
            external_id=guid,
            title=str(raw["title"]),
            url=str(raw.get("applicationLink") or guid),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=datetime.fromtimestamp(int(published), UTC) if published else None,
            content_hash=content_hash(description),
            company_name=str(raw["companyName"]) if raw.get("companyName") else None,
        )
