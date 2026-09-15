"""Registry coverage: which sponsor registers actually have a snapshot on this box.

SPEC §4 claimed the UK register was ingested; it never was. `_available_ingesters`
(`refresh.py`) skips a missing snapshot with a printed line and returns, so the absence was
invisible for sixteen slices while every `registry_inferred` tier in the corpus came from the
two registers that *had* been downloaded. This view exists so that the next missing snapshot
is visible the week it happens: it reports every registry bit, and states an absent snapshot
rather than omitting the row."""

from dataclasses import dataclass
from datetime import datetime

from beacon.application.ports import CompanyRepo, RegistriesMetaRepo
from beacon.domain.registry import SNAPSHOT_REGISTRIES, RegistryMeta, count_per_registry


@dataclass(frozen=True, slots=True)
class RegistryCoverageRow:
    """One register's standing. `fetched_at is None` means never ingested on this box — a
    different and worse state than `stale`, which is a snapshot that aged past the window."""

    registry: str
    fetched_at: datetime | None
    row_count: int | None
    companies: int  # seed companies carrying this bit
    stale: bool


@dataclass(frozen=True, slots=True)
class RegistryCoverageView:
    registries: tuple[RegistryCoverageRow, ...]


def get_registry_coverage(
    meta_repo: RegistriesMetaRepo, company_repo: CompanyRepo, *, now: datetime
) -> RegistryCoverageView:
    snapshots: dict[str, RegistryMeta] = {meta.registry: meta for meta in meta_repo.list_all()}
    matched = count_per_registry(company_repo.count_by_registry_flags())
    rows = tuple(
        _row(registry.name, snapshots.get(registry.name), matched.get(registry, 0), now=now)
        for registry in SNAPSHOT_REGISTRIES
        if registry.name is not None
    )
    return RegistryCoverageView(registries=rows)


def _row(
    name: str, snapshot: RegistryMeta | None, companies: int, *, now: datetime
) -> RegistryCoverageRow:
    return RegistryCoverageRow(
        registry=name,
        fetched_at=snapshot.fetched_at if snapshot else None,
        row_count=snapshot.row_count if snapshot else None,
        companies=companies,
        # A register that was never ingested is not "stale" — nothing aged out. The UI has to
        # be able to tell the two apart, so this stays False and fetched_at carries the news.
        stale=snapshot.is_stale(now=now) if snapshot else False,
    )
