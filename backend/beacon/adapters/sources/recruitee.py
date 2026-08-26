"""Recruitee public offers API (no auth) — one seed company per adapter.

Single call per board: `{slug}.recruitee.com/api/offers/` returns the ad text inline, so
unlike SmartRecruiters/Workday there is no detail step. NL-origin ATS, which is why it is
here — it is where Benelux employers of Beacon's size post.

Two board quirks worth naming: the ad is split across `description` and `requirements`
(both halves carry real copy, so both are the description), and `published_at` is written
"2026-06-02 10:10:41 UTC" — a space instead of the T and a literal zone name, which
fromisoformat does not accept.
"""

from datetime import UTC, datetime
from typing import Any

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_OFFERS = "https://{slug}.recruitee.com/api/offers/"
_PUBLISHED_FORMAT = "%Y-%m-%d %H:%M:%S %Z"


class RecruiteeAdapter:
    source_id = "recruitee"

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._slug = slug
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        data = await self._fetcher.get_json(_OFFERS.format(slug=self._slug))
        offers: list[RawPosting] = data.get("offers") or []
        return offers

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        location_raw = str(raw.get("location") or "")
        country, city = self._place(raw, location_raw)
        description = normalize_description(
            " ".join(
                str(raw.get(part) or "").strip()
                for part in ("description", "requirements")
                if raw.get(part)
            )
        )
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["id"]),
            title=str(raw["title"]),
            url=str(raw.get("careers_url") or raw.get("careers_apply_url") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=self._published_at(raw),
            content_hash=content_hash(description),
        )

    @staticmethod
    def _place(raw: RawPosting, location_raw: str) -> tuple[str | None, str | None]:
        """`country_code` is the board's own ISO-2 and is authoritative; the string parser is
        only the fallback for a board that left it empty."""
        code = str(raw.get("country_code") or "")
        city = str(raw.get("city") or "") or None
        if len(code) == 2 and code.isalpha():
            return code.upper(), city
        parsed_country, parsed_city = parse_location(location_raw)
        return parsed_country, city or parsed_city

    @staticmethod
    def _published_at(raw: RawPosting) -> datetime | None:
        stamp = raw.get("published_at") or raw.get("created_at")
        return _parse_utc(stamp) if stamp else None


def _parse_utc(stamp: Any) -> datetime | None:
    """ "2026-06-02 10:10:41 UTC" → aware UTC. An unparseable stamp stays None rather than
    becoming a fabricated date (SPEC: posted_at may legitimately be null)."""
    try:
        return datetime.strptime(str(stamp), _PUBLISHED_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None
