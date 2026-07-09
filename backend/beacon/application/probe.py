"""The weekly restore probe (SPEC §7).

Quarantined sources are skipped by the regular poll, so without a probe they'd never recover
from a temporary outage or DNS blip. Once a week this retries each quarantined source exactly
once: a clean poll restores it to ok (and resumes upserting), a failed probe leaves it
quarantined with its counters untouched — a probe never pushes a source deeper."""

import logging
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ingest import SourceFactory, ingest_source
from beacon.application.ports import Classifier, CompanyRepo, JobRepo
from beacon.domain.health import record_success

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    probed: int
    restored: int


async def probe_quarantined(
    company_repo: CompanyRepo,
    jobs: JobRepo,
    source_for: SourceFactory,
    classifier: Classifier,
    *,
    now: datetime,
) -> ProbeResult:
    quarantined = company_repo.list_quarantined()
    restored = 0
    for company in quarantined:
        source = source_for(company)
        if source is None or company.id is None:
            continue
        result = await ingest_source(source, company, jobs, classifier, now=now)
        if result.failure is None:
            state = company_repo.get_health(company.id)
            company_repo.set_health(company.id, record_success(state, now=now))
            restored += 1
            logger.info("probe_restored company=%s", company.name)
        else:
            # Still down — leave the quarantine and its counters exactly as they were.
            logger.info("probe_still_down company=%s kind=%s", company.name, result.failure)
    return ProbeResult(probed=len(quarantined), restored=restored)
