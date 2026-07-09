"""Assemble the digest's source-health section (SPEC §7): quarantined sources and stale
registry snapshots, translated from repo read models into digest value objects. Pure wiring
over two reads — the thresholds/staleness logic live in the domain."""

from datetime import datetime

from beacon.application.ports import CompanyRepo, RegistriesMetaRepo
from beacon.domain.digest import HealthAlert, RegistryStale
from beacon.domain.health import Health
from beacon.domain.registry import stale_registries


def build_health_alerts(
    company_repo: CompanyRepo, meta_repo: RegistriesMetaRepo, *, now: datetime
) -> tuple[tuple[HealthAlert, ...], tuple[RegistryStale, ...]]:
    """Quarantined-source alerts and stale-registry warnings for the digest. Empty tuples when
    everything is healthy (a healthy state adds nothing to the digest)."""
    alerts = tuple(
        HealthAlert(
            company=company.name,
            reason=company.reason or Health.QUARANTINED.value,
            since=(
                company.last_success_at.date().isoformat()
                if company.last_success_at is not None
                else "never"
            ),
        )
        for company in company_repo.list_health()
        if company.health == Health.QUARANTINED.value
    )
    stale = tuple(
        RegistryStale(registry=meta.registry, fetched_at=meta.fetched_at.date().isoformat())
        for meta in stale_registries(meta_repo.list_all(), now=now)
    )
    return alerts, stale
