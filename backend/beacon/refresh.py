"""CLI composition root for registry operations. Wiring only.

python -m beacon.refresh
    Match every seed company against the available registry snapshots and update
    registry_flags / match_confidence / job tiers.

python -m beacon.refresh --flag "Lovable" --evidence "listed on relocate.me"
    Hand-flag one company as a MANUAL sponsor (confidence 1.0, no fuzzy matching).
"""

import argparse
import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.persistence.registries_meta import SqliteRegistriesMetaRepo
from beacon.adapters.registries.ca import CALMIARegistry
from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ie import IEPermitsRegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.adapters.seeds import parse_seed_csv
from beacon.application.flag_sponsor import flag_manual_sponsor
from beacon.application.ports import RegistryIngester
from beacon.application.refresh_registries import refresh_registries
from beacon.config import Settings
from beacon.domain.registry import registries_needing_refresh
from beacon.logging_setup import configure_cli_logging

logger = logging.getLogger(__name__)


# Where each register's hand-downloaded snapshot is expected, and where it comes from. The
# source is named in the skip line because a missing file is the single reason UK/NL/US have
# never been ingested — for sixteen slices that failure was one quiet "skip" among five.
_SNAPSHOT_SOURCES: dict[str, str] = {
    "UK": "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers",
    "NL": "https://ind.nl/en/public-register-recognised-sponsors (no bulk export — hand-build)",
    "US": "https://www.dol.gov/agencies/eta/foreign-labor/performance (XLSX, export to CSV)",
    "IE": "https://enterprise.gov.ie employment-permits-issued-to-companies-<year>.xlsx",
    "CA": "https://open.canada.ca TFWP positive-LMIA employers",
}


# One registry's snapshot: its bitmask name, where the file is expected, and how to read it.
_SnapshotSpec = tuple[str, Path, Callable[[Path], RegistryIngester]]


def _snapshot_specs(settings: Settings) -> tuple[_SnapshotSpec, ...]:
    return (
        ("UK", settings.uk_registry_path, UKSponsorRegistry),
        ("NL", settings.ind_registry_path, INDRegistry),
        ("US", settings.h1b_registry_path, H1BLCARegistry),
        ("IE", settings.ie_registry_path, IEPermitsRegistry),
        ("CA", settings.ca_registry_path, CALMIARegistry),
    )


def report_missing_snapshots(settings: Settings) -> tuple[str, ...]:
    """Name every register whose file is absent, and where to get it.

    Absence is the content. `_available_ingesters` skips a missing file by design, which is how
    SPEC §4 came to claim the UK register was ingested while its bit sat on zero companies for
    sixteen slices. No re-run fixes a missing file — it is a hand download — so the line says so.
    """
    missing = tuple(name for name, path, _ in _snapshot_specs(settings) if not path.exists())
    for name in missing:
        print(f"MISSING registry snapshot {name}: never ingested — no file on this box")
        print(f"    download: {_SNAPSHOT_SOURCES[name]}")
    return missing


def _available_ingesters(settings: Settings) -> list[RegistryIngester]:
    """Only the snapshots that are actually present — a missing register is skipped, not fatal."""
    report_missing_snapshots(settings)
    return [build(path) for _name, path, build in _snapshot_specs(settings) if path.exists()]


def available_registry_names(settings: Settings) -> tuple[str, ...]:
    """The registers whose snapshot file is on disk — the only ones a refresh could ingest."""
    return tuple(name for name, path, _ in _snapshot_specs(settings) if path.exists())


def run_refresh_if_needed(settings: Settings) -> int:
    """Refresh only when a present snapshot has never been ingested, or has gone stale.

    Called at launch, so a file dropped into data/registries/ is picked up the next time Beacon
    starts rather than on the 1st of next month. Matching every seed company is not free, so a
    launch with nothing to do says so and returns.
    """
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    meta_repo = SqliteRegistriesMetaRepo(conn)
    wanted = registries_needing_refresh(
        available_registry_names(settings), meta_repo.list_all(), now=datetime.now(UTC)
    )
    if not wanted:
        # "Up to date" is true of what is here and says nothing about what is not, so the
        # absent registers are named on every launch, not only when a refresh happens.
        report_missing_snapshots(settings)
        print("registries up to date — no refresh needed")
        return 0
    print(f"registries needing ingest: {', '.join(wanted)} — refreshing now")
    return run_refresh(settings)


def _wire(settings: Settings) -> tuple[sqlite3.Connection, SqliteCompanyRepo, SqliteJobRepo]:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    company_repo = SqliteCompanyRepo(conn)
    for seed in parse_seed_csv(settings.seeds_path.read_text()):
        company_repo.upsert(seed)
    return conn, company_repo, SqliteJobRepo(conn)


def run_refresh(settings: Settings) -> int:
    conn, company_repo, jobs = _wire(settings)
    ingesters = _available_ingesters(settings)
    if not ingesters:
        print("no registry snapshots available — nothing to match")
        return 1
    result = refresh_registries(
        company_repo.list_active(),
        ingesters,
        company_repo,
        jobs,
        meta_repo=SqliteRegistriesMetaRepo(conn),
        now=datetime.now(UTC),
    )
    print(f"refresh companies={result.companies} matched={result.matched}")
    return 0


def _run_flag(settings: Settings, name: str, evidence: str) -> int:
    _conn, company_repo, jobs = _wire(settings)
    try:
        flag_manual_sponsor(company_repo, jobs, name, evidence, flagged_on=datetime.now(UTC).date())
    except ValueError as error:
        print(str(error))
        return 1
    print(f"flagged MANUAL sponsor: {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh sponsor registries, or flag one company as a MANUAL sponsor."
    )
    parser.add_argument("--flag", metavar="NAME", help="flag this company as a MANUAL sponsor")
    parser.add_argument("--evidence", help="evidence note (required with --flag)")
    args = parser.parse_args(argv)

    configure_cli_logging()
    settings = Settings.from_env()
    if args.flag is not None:
        if not args.evidence:
            parser.error("--evidence is required with --flag")
        return _run_flag(settings, args.flag, args.evidence)
    return run_refresh(settings)


if __name__ == "__main__":
    raise SystemExit(main())
