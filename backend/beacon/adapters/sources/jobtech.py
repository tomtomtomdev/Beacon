"""JobTech (Arbetsförmedlingen JobSearch API) as a company-less JobSource.

Sweden's national job board API. Each hit names its own employer, so jobs carry
company_name. Country defaults to SE when the hit omits a country_code (the API's
own default); a hit that names another country keeps it.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob

_SEARCH_API = "https://jobsearch.api.jobtechdev.se/search"
_AD_URL = "https://arbetsformedlingen.se/platsbanken/annonser/{id}"
_DEFAULT_COUNTRY = "SE"
# JobTech emits publication_date without an offset; the ad clock is Swedish local time.
_SOURCE_TZ = ZoneInfo("Europe/Stockholm")


class JobTechAdapter:
    source_id = "jobtech"

    def __init__(self, fetcher: Fetcher, *, limit: int = 100) -> None:
        self._fetcher = fetcher
        self._limit = limit

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(_SEARCH_API, params={"limit": str(self._limit)})
        hits: list[RawPosting] = data["hits"]
        return hits

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        address = raw.get("workplace_address") or {}
        country = str(address.get("country_code") or _DEFAULT_COUNTRY).upper()
        city = address.get("municipality") or None
        location_raw = ", ".join(p for p in (city, address.get("country")) if p) or country

        block = raw.get("description") or {}
        description = normalize_description(
            str(block.get("text_formatted") or block.get("text") or "")
        )
        employer = raw.get("employer") or {}
        item_id = str(raw["id"])
        return NormalizedJob(
            source_id=self.source_id,
            external_id=item_id,
            title=str(raw["headline"]),
            url=str(raw.get("webpage_url") or _AD_URL.format(id=item_id)),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=_parse_published(raw.get("publication_date")),
            content_hash=content_hash(description),
            company_name=str(employer["name"]) if employer.get("name") else None,
        )


def _parse_published(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:  # no offset → interpret in the source's local timezone
        parsed = parsed.replace(tzinfo=_SOURCE_TZ)
    return parsed.astimezone(UTC)
