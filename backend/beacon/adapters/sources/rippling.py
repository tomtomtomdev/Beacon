"""Rippling ATS public board (no auth) — one seed company per adapter.

Two-step by necessity: `board/{slug}/jobs` lists uuid/name/url/workLocation only, so the ad
text comes from `board/{slug}/jobs/{uuid}` — without it there is no content_hash, no
sponsorship tier and no resume score, which is the same trade slice 13 accepted for
SmartRecruiters and Workday. The list repeats a posting once per work location, so the uuid
is the identity and the list is deduped before any detail call is spent.

A detail that fails is skipped, not fatal: the list is a snapshot and a posting can close
between the two calls, so one dead uuid must not cost the whole poll (CLAUDE.md rule 6).
The detail's description arrives as {"company": html, "role": html} — both halves are the ad.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from beacon.application.errors import SourceUnavailable
from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

logger = logging.getLogger(__name__)

_BOARD = "https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
# Ad halves in reading order; a posting may carry either.
_DESCRIPTION_PARTS = ("company", "role")


class RipplingAdapter:
    source_id = "rippling"

    def __init__(self, slug: str, fetcher: Fetcher) -> None:
        self._slug = slug
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        details: list[RawPosting] = []
        for uuid in await self._list_uuids():
            detail = await self._detail(uuid)
            if detail is not None:
                details.append(detail)
        return details

    async def _list_uuids(self) -> list[str]:
        rows = await self._fetcher.get_json(_BOARD.format(slug=self._slug))
        # dict.fromkeys keeps the board's own order while dropping the per-location repeats.
        return list(dict.fromkeys(str(row["uuid"]) for row in rows))

    async def _detail(self, uuid: str) -> RawPosting | None:
        url = f"{_BOARD.format(slug=self._slug)}/{uuid}"
        try:
            detail: RawPosting = await self._fetcher.get_json(url)
        except SourceUnavailable as error:
            logger.info(
                "rippling_detail_skipped slug=%s uuid=%s kind=%s",
                self._slug,
                uuid,
                error.kind.value,
            )
            return None
        return detail

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        places = [str(place) for place in (raw.get("workLocations") or [])]
        location_raw = "; ".join(places)
        country, city = parse_location(places[0]) if places else (None, None)
        description = normalize_description(_ad_text(raw))
        created = raw.get("createdOn")
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw["uuid"]),
            title=str(raw["name"]),
            url=str(raw.get("url") or ""),
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            # ISO-8601 with a real offset ("…-07:00") — converted, never truncated.
            posted_at=datetime.fromisoformat(str(created)).astimezone(UTC) if created else None,
            content_hash=content_hash(description),
        )


def _ad_text(raw: RawPosting) -> str:
    description: Any = raw.get("description") or {}
    if isinstance(description, str):
        return description
    return " ".join(
        str(description.get(part) or "").strip()
        for part in _DESCRIPTION_PARTS
        if description.get(part)
    )
