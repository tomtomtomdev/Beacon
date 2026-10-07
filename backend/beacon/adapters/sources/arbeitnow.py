"""Arbeitnow job-board API as a company-less JobSource (SPEC §5.4).

No auth, ~325 rows a page, newest `created_at` first. Attribution: the API's terms ask for a
link back, so every posting keeps its arbeitnow.com URL as the job link.

`search=` is ignored by the API (probed 2026-10-07), so the board cannot be steered by role.
`visa_sponsorship=true` is honoured and is always sent: it narrows which postings Beacon pays
to ingest. It is a fetch filter, never a tier claim — rows carry no per-posting visa field, so
the tier is still resolved from description text and the registries like any other source.
"""

import logging
from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

_API = "https://www.arbeitnow.com/api/job-board-api"
_VISA_SPONSORSHIP_ONLY = {"visa_sponsorship": "true"}
_MAX_PAGES = 3  # ~975 newest postings per poll; older ones were ingested by earlier polls


class ArbeitnowAdapter:
    source_id = "arbeitnow"

    def __init__(self, fetcher: Fetcher, *, max_pages: int = _MAX_PAGES) -> None:
        self._fetcher = fetcher
        self._max_pages = max_pages

    async def fetch(self) -> list[RawPosting]:
        by_slug: dict[str, RawPosting] = {}
        for page in range(1, self._max_pages + 1):
            # The page number is sent explicitly rather than following `links.next` verbatim,
            # which keeps each conditional-GET cache key a clean (url, params) pair.
            data = await self._fetcher.get_json(
                _API, params={**_VISA_SPONSORSHIP_ONLY, "page": str(page)}
            )
            for raw in data["data"]:
                # Newest-first paging shifts under a mid-walk publish; a slug lands once.
                by_slug.setdefault(str(raw["slug"]), raw)
            if not data["links"].get("next"):
                return list(by_slug.values())
        # Paging stopped at the cap, not at the end of the board — say so rather than letting
        # a partial sweep look complete.
        logger.info("arbeitnow_page_cap fetched=%d", len(by_slug))
        return list(by_slug.values())

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = str(raw.get("location") or "")
        country, city = parse_location(location_raw)
        description = normalize_description(str(raw.get("description") or ""))
        created = raw.get("created_at")  # unix epoch seconds
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["slug"]),
            title=str(raw["title"]),
            url=str(raw["url"]),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=datetime.fromtimestamp(int(created), UTC) if created else None,
            content_hash=content_hash(description),
            company_name=str(raw["company_name"]) if raw.get("company_name") else None,
        )
