"""CLI composition root for registry operations. Wiring only.

python -m beacon.refresh
    Match every seed company against the available registry snapshots and update
    registry_flags / match_confidence / job tiers.

python -m beacon.refresh --flag "Lovable" --evidence "listed on relocate.me"
    Hand-flag one company as a MANUAL sponsor (confidence 1.0, no fuzzy matching).
"""

import argparse
import logging
from datetime import UTC, datetime

from beacon.adapters.persistence.companies import SqliteCompanyRepo
from beacon.adapters.persistence.db import MIGRATIONS_DIR, connect, run_migrations
from beacon.adapters.persistence.jobs import SqliteJobRepo
from beacon.adapters.registries.h1b import H1BLCARegistry
from beacon.adapters.registries.ind import INDRegistry
from beacon.adapters.registries.uk import UKSponsorRegistry
from beacon.adapters.seeds import parse_seed_csv
from beacon.application.flag_sponsor import flag_manual_sponsor
from beacon.application.ports import RegistryIngester
from beacon.application.refresh_registries import refresh_registries
from beacon.config import Settings

logger = logging.getLogger(__name__)


def _available_ingesters(settings: Settings) -> list[RegistryIngester]:
    """Only the snapshots that are actually present — a missing register is skipped, not fatal."""
    ingesters: list[RegistryIngester] = []
    for path, build in (
        (settings.uk_registry_path, UKSponsorRegistry),
        (settings.ind_registry_path, INDRegistry),
        (settings.h1b_registry_path, H1BLCARegistry),
    ):
        if path.exists():
            ingesters.append(build(path))
        else:
            print(f"skip registry snapshot (not found): {path}")
    return ingesters


def _wire(settings: Settings) -> tuple[SqliteCompanyRepo, SqliteJobRepo]:
    conn = connect(settings.db_path)
    run_migrations(conn, MIGRATIONS_DIR)
    company_repo = SqliteCompanyRepo(conn)
    for seed in parse_seed_csv(settings.seeds_path.read_text()):
        company_repo.upsert(seed)
    return company_repo, SqliteJobRepo(conn)


def _run_refresh(settings: Settings) -> int:
    company_repo, jobs = _wire(settings)
    ingesters = _available_ingesters(settings)
    if not ingesters:
        print("no registry snapshots available — nothing to match")
        return 1
    result = refresh_registries(company_repo.list_active(), ingesters, company_repo, jobs)
    print(f"refresh companies={result.companies} matched={result.matched}")
    return 0


def _run_flag(settings: Settings, name: str, evidence: str) -> int:
    company_repo, jobs = _wire(settings)
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

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    if args.flag is not None:
        if not args.evidence:
            parser.error("--evidence is required with --flag")
        return _run_flag(settings, args.flag, args.evidence)
    return _run_refresh(settings)


if __name__ == "__main__":
    raise SystemExit(main())
