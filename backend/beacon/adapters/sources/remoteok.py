"""RemoteOK (public JSON API) as a company-less JobSource.

The API returns a JSON array whose first element is a legal-notice object (no id); every
other element is a posting that names its own employer, so jobs carry company_name.
Locations are free text ("Worldwide", "Europe", "United States") → parse_location, which
stays country-less on regions rather than fabricating one.
"""

from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_API = "https://remoteok.com/api"


class RemoteOKAdapter:
    source_id = "remoteok"

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(_API)
        # Drop the leading legal-notice object (it has no "id"); keep real postings.
        return [item for item in data if isinstance(item, dict) and item.get("id")]

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = str(raw.get("location") or "")
        country, city = parse_location(location_raw)
        description = normalize_description(str(raw.get("description") or ""))
        company = raw.get("company")
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["position"]),
            url=str(raw["url"]),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=_parse_date(raw.get("date")),
            content_hash=content_hash(description),
            company_name=str(company) if company else None,
        )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
