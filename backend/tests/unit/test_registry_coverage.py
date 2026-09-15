"""Registry coverage: which sponsor registers actually have a snapshot on this box.

The bug this exists to make impossible: SPEC §4 claimed the UK register was ingested and it
never was — `_available_ingesters` skips a missing snapshot with a print line, so the absence
was invisible for sixteen slices. Coverage therefore reports *every* bit, and an absent
snapshot is a stated "never ingested", not a missing row.
"""

from datetime import UTC, datetime, timedelta

from beacon.application.ports import CompanyRepo, RegistriesMetaRepo
from beacon.application.registry_coverage import RegistryCoverageRow, get_registry_coverage
from beacon.domain.registry import REGISTRY_STALE_AFTER_DAYS, Registry, RegistryMeta
from tests.unit.fakes import StubCompanyRepo, StubRegistriesMetaRepo

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def meta(registry: str, *, days_ago: int, row_count: int = 100) -> RegistryMeta:
    return RegistryMeta(
        registry=registry, fetched_at=NOW - timedelta(days=days_ago), row_count=row_count
    )


def coverage(
    *,
    metas: list[RegistryMeta] | None = None,
    flag_counts: dict[int, int] | None = None,
) -> dict[str, RegistryCoverageRow]:
    meta_repo: RegistriesMetaRepo = StubRegistriesMetaRepo(metas)
    company_repo: CompanyRepo = StubCompanyRepo(registry_flag_counts=flag_counts)
    view = get_registry_coverage(meta_repo, company_repo, now=NOW)
    return {row.registry: row for row in view.registries}


def test_a_registry_with_no_snapshot_is_reported_as_never_ingested() -> None:
    rows = coverage(metas=[meta("IE", days_ago=11)])

    assert rows["IE"].fetched_at == NOW - timedelta(days=11)
    uk = rows["UK"]
    assert uk.fetched_at is None
    assert uk.row_count is None


def test_coverage_lists_every_registry_bit_except_the_hand_flag() -> None:
    # The exhaustiveness guard (18d's test_every_country_has_a_pin in spirit): a bit appended
    # to the enum must show up here without anyone remembering to add it. MANUAL is excluded
    # because it is the --flag bit, not a published register — reporting it as a missing
    # snapshot would be a second lie in a slice about not lying.
    rows = coverage()

    assert set(rows) == {r.name for r in Registry} - {Registry.MANUAL.name}


def test_coverage_counts_companies_per_bit() -> None:
    # A company carrying IE|CA counts once for each, which is why the count cannot be a
    # GROUP BY registry_flags passed straight through.
    rows = coverage(
        flag_counts={
            int(Registry.IE): 20,
            int(Registry.CA): 9,
            int(Registry.IE | Registry.CA): 1,
            0: 2140,
        }
    )

    assert rows["IE"].companies == 21
    assert rows["CA"].companies == 10
    assert rows["UK"].companies == 0


def test_a_snapshot_older_than_the_window_is_stale() -> None:
    rows = coverage(
        metas=[
            meta("IE", days_ago=REGISTRY_STALE_AFTER_DAYS + 1),
            meta("CA", days_ago=REGISTRY_STALE_AFTER_DAYS - 1),
        ]
    )

    assert rows["IE"].stale is True
    assert rows["CA"].stale is False


def test_a_registry_that_was_never_ingested_is_not_called_stale() -> None:
    # "Stale" means a snapshot aged out; "never ingested" is a different, worse state and the
    # UI has to be able to tell them apart.
    rows = coverage()

    assert rows["UK"].stale is False
    assert rows["UK"].fetched_at is None
