"""Workable's public account widget — one seed company per adapter.

`GET apply.workable.com/api/v1/widget/accounts/{slug}?details=true` returns the whole board
with descriptions inline, so one request per poll is enough (no per-posting detail fetch).
The v3 accounts endpoint is not public — v1 widget is the supported public path.
"""

from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_WIDGET = "https://apply.workable.com/api/v1/widget/accounts/{slug}"


class WorkableAdapter:
    source_id = "workable"

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._slug = slug
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(
            _WIDGET.format(slug=self._slug), params={"details": "true"}
        )
        jobs: list[RawPosting] = data["jobs"]
        return jobs

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = ", ".join(
            str(part) for part in (raw.get("city"), raw.get("state"), raw.get("country")) if part
        )
        country, city = _place(raw, location_raw)
        description = normalize_description(str(raw.get("description") or ""))
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["shortcode"]),
            title=str(raw["title"]),
            url=str(raw.get("url") or raw.get("shortlink") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=_posted_at(raw),
            content_hash=content_hash(description),
        )


def _place(raw: RawPosting, location_raw: str) -> tuple[str | None, str | None]:
    """locations[] carries an explicit ISO-2 countryCode; the flat city/country strings are
    the fallback for boards that omit it."""
    locations = raw.get("locations") or []
    first = locations[0] if locations else {}
    code = str(first.get("countryCode") or "")
    city = str(raw.get("city") or first.get("city") or "") or None
    if len(code) == 2 and code.isalpha():
        return code.upper(), city
    parsed_country, parsed_city = parse_location(location_raw)
    return parsed_country, city or parsed_city


def _posted_at(raw: RawPosting) -> datetime | None:
    """published_on is a bare date (no clock) — read as midnight UTC. Absent → None."""
    published = raw.get("published_on") or raw.get("created_at")
    if not published:
        return None
    return datetime.fromisoformat(str(published)).replace(tzinfo=UTC)
