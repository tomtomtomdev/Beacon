"""We Work Remotely (RSS/XML) as a company-less JobSource.

WWR publishes a trusted RSS feed (SPEC §5.2 — not hostile HTML scraping). fetch() pulls the
raw XML and reduces each <item> to a plain dict; normalize() maps that dict to a job. The
item title is "Company: Role", so the employer is parsed off the front (company-less source).
"""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from beacon.application.ports import Fetcher, RawPosting
from beacon.domain.descriptions import content_hash, normalize_description
from beacon.domain.job import NormalizedJob
from beacon.domain.location import parse_location

_FEED = "https://weworkremotely.com/remote-jobs.rss"


class WWRAdapter:
    source_id = "weworkremotely"

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    async def fetch(self) -> list[RawPosting]:
        xml = await self._fetcher.get_text(_FEED)
        return _parse_items(xml)

    def normalize(self, raw: RawPosting) -> NormalizedJob:
        company, title = _split_company(str(raw.get("title") or ""))
        location_raw = str(raw.get("region") or "")
        country, city = parse_location(location_raw)
        description = normalize_description(str(raw.get("description") or ""))
        url = str(raw.get("link") or "")
        return NormalizedJob(
            source_id=self.source_id,
            external_id=str(raw.get("guid") or url),
            title=title,
            url=url,
            description=description,
            location_raw=location_raw,
            country=country,
            city=city,
            posted_at=_parse_pubdate(raw.get("pubDate")),
            content_hash=content_hash(description),
            company_name=company,
        )


def _parse_items(xml: str) -> list[RawPosting]:
    root = ElementTree.fromstring(xml)
    items: list[RawPosting] = []
    for item in root.iter("item"):
        items.append({child.tag: (child.text or "") for child in item})
    return items


def _split_company(title: str) -> tuple[str | None, str]:
    """'Company: Role' → ('Company', 'Role'); a title without the colon keeps the whole
    string and attributes no employer (that posting is skipped by the company-less ingest)."""
    company, sep, role = title.partition(": ")
    if sep:
        return company.strip(), role.strip()
    return None, title.strip()


def _parse_pubdate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
