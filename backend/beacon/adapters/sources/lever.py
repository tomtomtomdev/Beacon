from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_POSTINGS_API = "https://api.lever.co/v0/postings/{slug}"


class LeverAdapter:
    source_id = "lever"

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._slug = slug
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        # Lever returns a bare JSON array (no envelope).
        data = await self._fetcher.get_json(
            _POSTINGS_API.format(slug=self._slug), params={"mode": "json"}
        )
        postings: list[RawPosting] = data
        return postings

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = str((raw.get("categories") or {}).get("location") or "")
        parsed_country, city = parse_location(location_raw)
        description = normalize_description(str(raw.get("description") or ""))
        created_at = raw.get("createdAt")  # epoch milliseconds, may be absent
        posted_at = (
            datetime.fromtimestamp(created_at / 1000, tz=UTC) if created_at is not None else None
        )
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["text"]),
            url=str(raw["hostedUrl"]),
            description=description,
            location_raw=location_raw,
            country=_iso2(raw.get("country")) or parsed_country,
            city=city,
            posted_at=posted_at,
            content_hash=content_hash(description),
        )


def _iso2(value: object) -> str | None:
    """Lever's country is usually a clean ISO-2 code; trust it only when it looks like one."""
    if isinstance(value, str) and len(value) == 2 and value.isalpha():
        return value.upper()
    return None
