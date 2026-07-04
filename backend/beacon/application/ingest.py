import logging
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import JobRepo, JobSource
from beacon.domain.company import Company

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestResult:
    fetched: int
    upserted: int
    errors: int


async def ingest_source(
    source: JobSource, company: Company, jobs: JobRepo, *, now: datetime
) -> IngestResult:
    """Fetch → normalize → upsert one company's board. One bad posting never kills the poll."""
    if company.id is None:
        raise ValueError(f"company {company.name!r} must be persisted before ingest")

    raw_postings = await source.fetch()
    upserted = errors = 0
    for raw in raw_postings:
        try:
            jobs.upsert(company.id, source.normalize(raw), seen_at=now)
            upserted += 1
        except Exception:
            errors += 1
            logger.exception(
                "posting_failed source=%s company=%s external_id=%s",
                source.source_id,
                company.name,
                raw.get("id", "?"),
            )

    logger.info(
        "poll source=%s company=%s fetched=%d upserted=%d errors=%d",
        source.source_id,
        company.name,
        len(raw_postings),
        upserted,
        errors,
    )
    return IngestResult(fetched=len(raw_postings), upserted=upserted, errors=errors)
