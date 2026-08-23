"""Teamtailor career sites — one seed company per adapter.

Every Teamtailor board serves a public JSON Feed at `{host}/jobs.json`: no key, full ad HTML,
and an embedded schema.org JobPosting whose address already carries an ISO-2 country. Boards
live on either a custom career domain ("careers.voi.com") or the tenant subdomain
("tibber.teamtailor.com"), so the seed slug accepts both — a dot means it's already a host.
"""

from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob

_FEED = "https://{host}/jobs.json"
_TENANT_HOST = "{slug}.teamtailor.com"


class TeamtailorAdapter:
    source_id = "teamtailor"

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._host = slug if "." in slug else _TENANT_HOST.format(slug=slug)
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(_FEED.format(host=self._host))
        items: list[RawPosting] = data["items"]
        return items

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        address = _address(raw)
        city = str(address.get("addressLocality") or "") or None
        code = str(address.get("addressCountry") or "") or None
        region = str(address.get("addressRegion") or "") or None
        location_raw = ", ".join(part for part in (city, region or code) if part)
        description = normalize_description(str(raw.get("content_html") or ""))
        published = raw.get("date_published") or (raw.get("_jobposting") or {}).get("datePosted")
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["title"]),
            url=str(raw.get("url") or ""),
            description=description,
            location_raw=location_raw,
            country=code.upper() if code else None,
            city=city,
            posted_at=datetime.fromisoformat(str(published)).astimezone(UTC) if published else None,
            content_hash=content_hash(description),
        )


def _address(raw: RawPosting) -> RawPosting:
    """The first place on the embedded JobPosting; a remote-anywhere ad has none."""
    locations = (raw.get("_jobposting") or {}).get("jobLocation") or []
    return (locations[0] if locations else {}).get("address") or {}
