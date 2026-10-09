"""Bundesagentur für Arbeit Jobsuche as a company-less JobSource (SPEC §5.4) — Germany's
official register, the DE twin of JobTech and NAV.

The `X-API-Key` header is a published public key and lives on the HTTP door keyed by host
(see `beacon.ingest`), so this adapter never holds a credential.

Two steps, because the list carries no ad text: the v6 `jobs` search, then the v4
`jobdetails/<base64(referenznummer)>` for `stellenangebotsBeschreibung` (v4/v5 `jobs` and v6
`jobdetails` answer 403). Refnrs are deduped across queries *before* the detail spend, and a
detail that fails is skipped and logged, never fatal (rule 6).

The search is fuzzy (`was=iOS Entwickler` also returns Product Owners), so its counts are
ceilings on spend, not on relevance. Measured 2026-10-07 (`maxErgebnisse`): "iOS Entwickler"
21, "iOS Developer" 14, "Swift Entwickler" 14, "Swift" 70, "iOS" 275, "Java Backend" 321,
"Java Entwickler" 355, "Backend Entwickler" 452, "Machine Learning Engineer" 126,
"Machine Learning" 630. The three narrow iOS phrasings go in whole; the backend and ML
families are capped at two pages of 50, so one poll spends at most ~250 detail calls at 1 rps
before dedup — under the ~300 polite budget of slice 13. "iOS"/"Swift" were rejected: bare
tokens buy hundreds of rows the iOS phrasings already cover.

Descriptions are German and the sponsorship regex is English, so DE rows mostly read
`unknown` — a recorded gap (PLAN 23d), to be closed by a vocabulary slice, not here.
"""

import logging
from base64 import b64encode
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import SecretStr

from beacon.application.errors import SourceUnavailable
from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

BUNDESAGENTUR_HOST = "rest.arbeitsagentur.de"
# Published by the Bundesagentur for its own web client — public, so not a setting. The
# ingest wiring puts it on the door as `X-API-Key`; this adapter never sends it itself.
BUNDESAGENTUR_API_KEY = SecretStr("jobboerse-jobsuche")
_SERVICE = f"https://{BUNDESAGENTUR_HOST}/jobboerse/jobsuche-service/pc"
_LIST = f"{_SERVICE}/v6/jobs"
_DETAIL = f"{_SERVICE}/v4/jobdetails/"
_JOB_PAGE = "https://www.arbeitsagentur.de/jobsuche/jobdetail/"
_GERMANY = "DEUTSCHLAND"

ROLE_QUERIES: tuple[str, ...] = (
    "iOS Entwickler",
    "iOS Developer",
    "Swift Entwickler",
    "Java Backend",
    "Machine Learning Engineer",
)
_PAGE_SIZE = 50
_MAX_PAGES = 2  # ≤100 rows per query per poll; the rest arrive on later polls


class BundesagenturAdapter:
    source_id = "bundesagentur"

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
        by_refnr: dict[str, RawPosting] = {}
        for query in self._queries:
            for row in await self._search(query):
                by_refnr.setdefault(str(row["referenznummer"]), row)
        postings: list[RawPosting] = []
        for refnr, row in by_refnr.items():
            detail = await self._detail(refnr)
            if detail is not None:
                # The detail repeats the list fields; the row fills in anything it omits.
                postings.append({**row, **detail})
        return postings

    async def _search(self, query: str) -> list[RawPosting]:
        found: list[RawPosting] = []
        total: int | None = None
        for page in range(1, self._max_pages + 1):
            data = await self._fetcher.get_json(
                _LIST, params={"was": query, "size": str(self._page_size), "page": str(page)}
            )
            rows: list[RawPosting] = data.get("ergebnisliste") or []
            total = data.get("maxErgebnisse")
            found.extend(rows)
            if len(rows) < self._page_size or (total is not None and len(found) >= total):
                return found
        # Paging stopped at the cap, not at the end of the results — say so rather than
        # letting a partial sweep look complete.
        logger.info("bundesagentur_page_cap query=%s fetched=%d total=%s", query, len(found), total)
        return found

    async def _detail(self, refnr: str) -> RawPosting | None:
        try:
            detail: RawPosting = await self._fetcher.get_json(f"{_DETAIL}{_detail_key(refnr)}")
        except SourceUnavailable as error:
            logger.info("bundesagentur_detail_skipped refnr=%s kind=%s", refnr, error.kind.value)
            return None
        return detail

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        refnr = str(raw["referenznummer"])
        address = ((raw.get("stellenlokationen") or [{}])[0]).get("adresse") or {}
        ort = str(address.get("ort") or "").strip()
        land = str(address.get("land") or "").strip()
        # `ort` reads "Freising, Oberbayern" or "Wien,Landstraße": the town comes first.
        city = ort.split(",")[0].strip() or None
        # DE is claimed only from the register's own DEUTSCHLAND; a foreign row's country is
        # whatever the town text names (Wien → AT), or nothing — never a defaulted DE.
        country = "DE" if land == _GERMANY else (parse_location(city)[0] if city else None)
        description = normalize_description(str(raw.get("stellenangebotsBeschreibung") or ""))
        published = raw.get("datumErsteVeroeffentlichung")
        firma = str(raw.get("firma") or "").strip()
        return NormalizedJob(
            source_id=self.source_id,
            external_id=refnr,
            title=str(raw["stellenangebotsTitel"]),
            url=f"{_JOB_PAGE}{refnr}",
            description=description,
            location_raw=", ".join(part for part in (ort, land) if part),
            country=country,
            city=city,
            posted_at=_midnight_utc(published),
            content_hash=content_hash(description),
            company_name=firma or None,
        )


def _detail_key(refnr: str) -> str:
    """The detail path takes the refnr as standard base64 of its ASCII bytes."""
    return b64encode(refnr.encode("ascii")).decode("ascii")


def _midnight_utc(published: object) -> datetime | None:
    if not published:
        return None
    day = datetime.strptime(str(published), "%Y-%m-%d")
    return day.replace(tzinfo=UTC)
