"""SmartRecruiters postings API (public, no auth) — one seed company per adapter.

Two-step by necessity: the list endpoint returns postings without their ad text, so fetch()
pages the list and then GETs each posting's detail. normalize() therefore reads a *detail*
payload, which is self-sufficient (location, releasedDate, jobAd sections). Detail calls go
through the shared polite door, so a large board (Grab: ~380 postings) spends its poll inside
the 1 rps per-host budget rather than bursting.
"""

from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_POSTINGS = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
_PAGE_LIMIT = 100
# Ad sections in reading order; a board may omit any of them.
_SECTIONS = ("companyDescription", "jobDescription", "qualifications", "additionalInformation")


class SmartRecruitersAdapter:
    source_id = "smartrecruiters"

    def __init__(self, slug: str, fetcher: Fetcher, *, page_limit: int = _PAGE_LIMIT) -> None:
        self._slug = slug
        self._fetcher = fetcher
        self._page_limit = page_limit

    async def fetch(self) -> list[RawPosting]:
        return [await self._detail(str(row["id"])) for row in await self._list_postings()]

    async def _list_postings(self) -> list[RawPosting]:
        url = _POSTINGS.format(slug=self._slug)
        rows: list[RawPosting] = []
        while True:
            page = await self._fetcher.get_json(
                url, params={"limit": str(self._page_limit), "offset": str(len(rows))}
            )
            content: list[RawPosting] = page["content"]
            rows.extend(content)
            if not content or len(rows) >= int(page.get("totalFound") or 0):
                return rows

    async def _detail(self, posting_id: str) -> RawPosting:
        url = f"{_POSTINGS.format(slug=self._slug)}/{posting_id}"
        detail: RawPosting = await self._fetcher.get_json(url)
        return detail

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location = raw.get("location") or {}
        location_raw = str(location.get("fullLocation") or "")
        country, city = _place(location, location_raw)
        description = normalize_description(_ad_text(raw))
        released = raw.get("releasedDate")  # ISO-8601, UTC 'Z'
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["name"]),
            url=str(raw.get("postingUrl") or raw.get("applyUrl") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=datetime.fromisoformat(released).astimezone(UTC) if released else None,
            content_hash=content_hash(description),
        )


def _place(location: RawPosting, location_raw: str) -> tuple[str | None, str | None]:
    """location.country is a lowercase ISO-2 code ("my"); anything else falls back to the
    shared string parser rather than guessing a code from a name."""
    code = str(location.get("country") or "")
    city = str(location.get("city") or "") or None
    if len(code) == 2 and code.isalpha():
        return code.upper(), city
    parsed_country, parsed_city = parse_location(location_raw)
    return parsed_country, city or parsed_city


def _ad_text(raw: RawPosting) -> str:
    sections = (raw.get("jobAd") or {}).get("sections") or {}
    return " ".join(
        str((sections.get(name) or {}).get("text") or "").strip()
        for name in _SECTIONS
        if (sections.get(name) or {}).get("text")
    )
