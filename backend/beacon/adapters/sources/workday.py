"""Workday CxS — the JSON a myworkdayjobs career site serves its own UI.

Seed slug is "tenant/wdN/site" (e.g. "clio/wd3/ClioCareerSite"), which is exactly what the
board URL already contains, so a seed row needs no new column. Two steps: the job list is
POST-only and caps at 20 rows per page, and the ad text lives on a per-posting GET (which
does carry ETags, so re-polls of unchanged postings revalidate cheaply).
"""

from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_CXS = "https://{tenant}.{instance}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
# Workday rejects a page larger than 20 with HTTP 400.
_PAGE_LIMIT = 20


class WorkdayAdapter:
    source_id = "workday"

    def __init__(self, slug: str, fetcher: Fetcher, *, page_limit: int = _PAGE_LIMIT) -> None:
        self._base = _cxs_base(slug)
        self._fetcher = fetcher
        self._page_limit = page_limit

    async def fetch(self) -> list[RawPosting]:
        return [await self._detail(str(row["externalPath"])) for row in await self._list_postings()]

    async def _list_postings(self) -> list[RawPosting]:
        rows: list[RawPosting] = []
        while True:
            page = await self._fetcher.post_json(
                f"{self._base}/jobs",
                json={
                    "appliedFacets": {},
                    "limit": self._page_limit,
                    "offset": len(rows),
                    "searchText": "",
                },
            )
            postings: list[RawPosting] = page["jobPostings"]
            rows.extend(postings)
            if not postings or len(rows) >= int(page.get("total") or 0):
                return rows

    async def _detail(self, external_path: str) -> RawPosting:
        detail: RawPosting = await self._fetcher.get_json(f"{self._base}{external_path}")
        return detail

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        info = raw["jobPostingInfo"]
        location_raw = ", ".join(
            str(part)
            for part in (info.get("location"), (info.get("country") or {}).get("descriptor"))
            if part
        )
        country, city = parse_location(location_raw)
        description = normalize_description(str(info.get("jobDescription") or ""))
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(info["id"]),
            title=str(info["title"]),
            url=str(info.get("externalUrl") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=_posted_at(info),
            content_hash=content_hash(description),
        )


def _cxs_base(slug: str) -> str:
    """ "clio/wd3/ClioCareerSite" → the tenant's CxS base URL."""
    parts = slug.split("/")
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"workday slug {slug!r} must be tenant/wdN/site")
    tenant, instance, site = parts
    return _CXS.format(tenant=tenant, instance=instance, site=site)


def _posted_at(info: RawPosting) -> datetime | None:
    """startDate is a bare date — midnight UTC. `postedOn` ("Posted 4 Days Ago") is relative
    prose with no anchor, so it is never used to fabricate a timestamp."""
    start = info.get("startDate")
    if not start:
        return None
    return datetime.fromisoformat(str(start)).replace(tzinfo=UTC)
