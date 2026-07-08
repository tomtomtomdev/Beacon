from datetime import UTC, datetime

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_JOB_BOARD_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class AshbyAdapter:
    source_id = "ashby"

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._slug = slug
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(_JOB_BOARD_API.format(slug=self._slug))
        jobs: list[RawPosting] = data["jobs"]
        return jobs

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = str(raw.get("location") or "")
        country, city = parse_location(location_raw)
        description = normalize_description(str(raw.get("descriptionHtml") or ""))
        published_at = raw.get("publishedAt")  # ISO-8601 with tz, may be absent
        posted_at = datetime.fromisoformat(published_at).astimezone(UTC) if published_at else None
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["title"]),
            url=str(raw["jobUrl"]),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=posted_at,
            content_hash=content_hash(description),
        )
