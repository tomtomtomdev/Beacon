from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_EU_BOARDS_API = "https://boards-api.eu.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseAdapter:
    source_id = "greenhouse"
    _boards_api = _BOARDS_API

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._slug = slug
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(
            self._boards_api.format(slug=self._slug), params={"content": "true"}
        )
        jobs: list[RawPosting] = data["jobs"]
        return jobs

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = str((raw.get("location") or {}).get("name") or "")
        country, city = parse_location(location_raw)
        description = normalize_description(str(raw.get("content") or ""))
        first_published = raw.get("first_published")
        posted_at = (
            datetime.fromisoformat(first_published).astimezone(UTC) if first_published else None
        )
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["title"]),
            url=str(raw["absolute_url"]),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=posted_at,
            content_hash=content_hash(description),
        )


class GreenhouseEUAdapter(GreenhouseAdapter):
    """Same board API and payload, hosted in Greenhouse's EU region (e.g. Binance). The slug
    does not say which region a board lives in, so the seed's ats_type does."""

    source_id = "greenhouse_eu"
    _boards_api = _EU_BOARDS_API
