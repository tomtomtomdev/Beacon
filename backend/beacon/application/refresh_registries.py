"""Cross-reference seed companies against the sponsor registries and write the results.

Sets companies.registry_flags / match_confidence / match_evidence, then re-resolves the
registry-derived tier on each company's jobs. A previously-set MANUAL flag is preserved:
fuzzy matching may add UK/NL/US bits but never clears MANUAL.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import CompanyRepo, JobRepo, RegistriesMetaRepo, RegistryIngester
from beacon.domain.company import Company
from beacon.domain.matching import match_company
from beacon.domain.registry import Registry
from beacon.domain.sponsorship import resolve_tier

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    companies: int
    matched: int


def refresh_registries(
    companies: Sequence[Company],
    ingesters: Sequence[RegistryIngester],
    company_repo: CompanyRepo,
    jobs: JobRepo,
    *,
    meta_repo: RegistriesMetaRepo | None = None,
    now: datetime | None = None,
) -> RefreshResult:
    entries_by_registry = {ingester.registry: ingester.fetch() for ingester in ingesters}

    # Record each snapshot's freshness so the digest can nag when one goes stale (SPEC §7).
    if meta_repo is not None and now is not None:
        for registry, entries in entries_by_registry.items():
            if registry.name is not None:
                meta_repo.record(registry.name, now, len(entries))

    matched = 0
    for company in companies:
        if company.id is None:
            continue
        result = match_company(company.name, entries_by_registry)
        manual_bit = Registry(company.registry_flags) & Registry.MANUAL
        if not result.flags and manual_bit:
            continue  # MANUAL-only company: leave its bit, confidence and evidence intact

        flags = result.flags | manual_bit
        confidence = 1.0 if manual_bit else result.confidence
        company_repo.set_registry_match(company.id, int(flags), confidence, result.evidence)
        jobs.resolve_registry_tier(company.id, resolve_tier(None, int(flags)).value)
        if flags:
            matched += 1

    logger.info(
        "refresh_registries companies=%d matched=%d registries=%d",
        len(companies),
        matched,
        len(entries_by_registry),
    )
    return RefreshResult(companies=len(companies), matched=matched)
