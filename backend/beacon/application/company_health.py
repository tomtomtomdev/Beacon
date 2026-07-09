"""The source-health view (DESIGN §3 / SPEC §7): every seed company's health plus summary
counts. A seed company whose ATS type has no adapter yet shows as 'pending' — it has never
been polled, so its stored health is not meaningful."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import CompanyHealth, CompanyRepo
from beacon.domain.health import Health

# A seed company whose ATS type has no adapter yet (smartrecruiters/workable/workday/…).
PENDING = "pending"


@dataclass(frozen=True, slots=True)
class CompanyHealthRow:
    name: str
    ats_type: str
    ats_slug: str
    country_hq: str
    status: str  # ok | degraded | quarantined | pending
    reason: str | None  # failure kind for degraded/quarantined; None otherwise
    last_success_at: datetime | None
    consecutive_failures: int


@dataclass(frozen=True, slots=True)
class HealthSummary:
    seed: int
    supported: int
    healthy: int
    degraded: int
    quarantined: int
    pending: int
    by_ats: dict[str, int]  # ats_type → count, for the seed line


@dataclass(frozen=True, slots=True)
class CompanyHealthView:
    summary: HealthSummary
    companies: tuple[CompanyHealthRow, ...]


def _status(company: CompanyHealth, supported_ats: Collection[str]) -> str:
    return company.health if company.ats_type in supported_ats else PENDING


def get_company_health(
    company_repo: CompanyRepo, supported_ats: Collection[str]
) -> CompanyHealthView:
    companies = company_repo.list_health()
    rows = tuple(
        CompanyHealthRow(
            name=company.name,
            ats_type=company.ats_type,
            ats_slug=company.ats_slug,
            country_hq=company.country_hq,
            status=_status(company, supported_ats),
            # A pending company was never polled — don't surface its default-'ok' health reason.
            reason=company.reason if company.ats_type in supported_ats else None,
            last_success_at=company.last_success_at,
            consecutive_failures=company.consecutive_failures,
        )
        for company in companies
    )
    statuses = [row.status for row in rows]
    by_ats: dict[str, int] = {}
    for company in companies:
        by_ats[company.ats_type] = by_ats.get(company.ats_type, 0) + 1
    summary = HealthSummary(
        seed=len(companies),
        supported=sum(1 for company in companies if company.ats_type in supported_ats),
        healthy=statuses.count(Health.OK.value),
        degraded=statuses.count(Health.DEGRADED.value),
        quarantined=statuses.count(Health.QUARANTINED.value),
        pending=statuses.count(PENDING),
        by_ats=by_ats,
    )
    return CompanyHealthView(summary=summary, companies=rows)
