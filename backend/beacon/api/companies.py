"""GET /companies/health — the source-health view (DESIGN §3): per-company health + summary
counts. Read-only; health is written by the ingest pipeline (SPEC §7)."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from beacon.adapters.sources.factory import SUPPORTED_ATS
from beacon.api.deps import CompanyRepoDep
from beacon.application.company_health import (
    CompanyHealthRow,
    CompanyHealthView,
    HealthSummary,
    get_company_health,
)

router = APIRouter()


class CompanyHealthRowOut(BaseModel):
    name: str
    ats_type: str
    ats_slug: str
    country_hq: str
    status: str
    reason: str | None
    last_success_at: datetime | None
    consecutive_failures: int


class HealthSummaryOut(BaseModel):
    seed: int
    supported: int
    healthy: int
    degraded: int
    quarantined: int
    pending: int
    by_ats: dict[str, int]


class CompanyHealthOut(BaseModel):
    summary: HealthSummaryOut
    companies: list[CompanyHealthRowOut]


@router.get("/companies/health")
def get_companies_health(repo: CompanyRepoDep) -> CompanyHealthOut:
    return _to_out(get_company_health(repo, SUPPORTED_ATS))


def _row_out(row: CompanyHealthRow) -> CompanyHealthRowOut:
    return CompanyHealthRowOut(
        name=row.name,
        ats_type=row.ats_type,
        ats_slug=row.ats_slug,
        country_hq=row.country_hq,
        status=row.status,
        reason=row.reason,
        last_success_at=row.last_success_at,
        consecutive_failures=row.consecutive_failures,
    )


def _summary_out(summary: HealthSummary) -> HealthSummaryOut:
    return HealthSummaryOut(
        seed=summary.seed,
        supported=summary.supported,
        healthy=summary.healthy,
        degraded=summary.degraded,
        quarantined=summary.quarantined,
        pending=summary.pending,
        by_ats=summary.by_ats,
    )


def _to_out(view: CompanyHealthView) -> CompanyHealthOut:
    return CompanyHealthOut(
        summary=_summary_out(view.summary),
        companies=[_row_out(row) for row in view.companies],
    )
