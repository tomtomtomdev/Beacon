"""MyCareersFuture — Singapore's official government job board — as a company-less JobSource.

Why it earns a slot despite modest volume (SPEC §4): Singapore is the springboard market with
no public sponsor register, and this board is the only source that ships an employer's salary
band as structured data, which is exactly what the Employment Pass threshold is measured
against. Search is POST-only and its rows carry no ad text, so each hit's detail is fetched.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

_SEARCH_API = "https://api.mycareersfuture.gov.sg/v2/search"
_JOB_API = "https://api.mycareersfuture.gov.sg/v2/jobs/{uuid}"
_HOME_COUNTRY = "SG"
_HOME_CITY = "Singapore"
# The three role families of SPEC §1, phrased as this board's search reads them. Data:
# widen coverage by editing the tuple, never the walk below.
ROLE_QUERIES: tuple[str, ...] = (
    "iOS engineer",
    "Java backend engineer",
    "machine learning engineer",
)
_PAGE_SIZE = 20
_MAX_PAGES = 3


class MyCareersFutureAdapter:
    source_id = "mycareersfuture"

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
        uuids: list[str] = []
        seen: set[str] = set()
        for query in self._queries:
            for row in await self._search(query):
                uuid = str(row["uuid"])
                if uuid not in seen:
                    seen.add(uuid)
                    uuids.append(uuid)
        return [await self._detail(uuid) for uuid in uuids]

    async def _search(self, query: str) -> list[RawPosting]:
        found: list[RawPosting] = []
        total: int | None = None
        for page in range(self._max_pages):
            data = await self._fetcher.post_json(
                _SEARCH_API,
                params={"limit": str(self._page_size), "page": str(page)},
                json={"search": query, "sessionId": "", "categories": []},
            )
            results: list[RawPosting] = data["results"]
            total = data.get("total")
            found.extend(results)
            if len(results) < self._page_size:
                return found
        # Stopped at the page cap rather than at the end of the results — never let a partial
        # sweep read as a complete one.
        logger.info(
            "mycareersfuture_page_cap query=%s fetched=%d total=%s", query, len(found), total
        )
        return found

    async def _detail(self, uuid: str) -> RawPosting:
        detail: RawPosting = await self._fetcher.get_json(_JOB_API.format(uuid=uuid))
        return detail

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        metadata = raw.get("metadata") or {}
        country, city, location_raw = _place(raw.get("address") or {})
        description = normalize_description(str(raw.get("description") or ""))
        posted = metadata.get("newPostingDate") or metadata.get("originalPostingDate")
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["uuid"]),
            title=str(raw["title"]),
            url=str(metadata.get("jobDetailsUrl") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            # A bare date — midnight UTC (Singapore's own clock isn't published on the field).
            posted_at=datetime.fromisoformat(str(posted)).replace(tzinfo=UTC) if posted else None,
            content_hash=content_hash(description),
            company_name=_employer(raw),
        )


def _place(address: RawPosting) -> tuple[str | None, str | None, str]:
    """A Singapore board: a posting is in Singapore unless flagged overseas, in which case
    only the named country is known (the street address is the employer's, not the role's)."""
    if not address.get("isOverseas"):
        return _HOME_COUNTRY, _HOME_CITY, _HOME_CITY
    named = str(address.get("overseasCountry") or "")
    country, city = parse_location(named)
    return country, city, named


def _employer(raw: RawPosting) -> str | None:
    """postedCompany is the hiring employer, except on an agency posting made on behalf of a
    named company — then the hiring company is the real employer."""
    for key in ("hiringCompany", "postedCompany"):
        name = (raw.get(key) or {}).get("name")
        if name:
            return str(name)
    return None
