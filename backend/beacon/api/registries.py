"""GET /registries — sponsor-registry coverage (DESIGN §1): which registers have a snapshot on
this box, how old it is, and how many seed companies it matched. Read-only; snapshots are
written by `refresh_registries` (SPEC §7)."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from beacon.api.deps import CompanyRepoDep, RegistriesMetaRepoDep
from beacon.application.registry_coverage import (
    RegistryCoverageRow,
    RegistryCoverageView,
    get_registry_coverage,
)

router = APIRouter()


class RegistryCoverageRowOut(BaseModel):
    registry: str
    # null = never ingested on this box, which is a different state from a stale snapshot.
    fetched_at: datetime | None
    row_count: int | None
    companies: int
    stale: bool


class RegistryCoverageOut(BaseModel):
    registries: list[RegistryCoverageRowOut]


@router.get("/registries")
def get_registries(repo: CompanyRepoDep, meta: RegistriesMetaRepoDep) -> RegistryCoverageOut:
    return _to_out(get_registry_coverage(meta, repo, now=datetime.now(UTC)))


def _row_out(row: RegistryCoverageRow) -> RegistryCoverageRowOut:
    return RegistryCoverageRowOut(
        registry=row.registry,
        fetched_at=row.fetched_at,
        row_count=row.row_count,
        companies=row.companies,
        stale=row.stale,
    )


def _to_out(view: RegistryCoverageView) -> RegistryCoverageOut:
    return RegistryCoverageOut(registries=[_row_out(row) for row in view.registries])
