"""CLI composition root for the unattended maintenance jobs: python -m beacon.maintenance <job>.

    refresh-registries   re-match seeds against the registry snapshots (monthly, SPEC §9)
    refresh-registries-if-needed
                         the same, but only when a present snapshot is un-ingested or stale
                         (run at launch by run.sh, off the monthly schedule)
    backup               timestamped SQLite copy, pruned to the newest 14 (nightly, SPEC §9)
    probe                retry quarantined sources so an outage self-heals (weekly, SPEC §7)

One launchd job per fire — deploy/com.beacon.{refresh,backup,probe}.plist — rather than cron
triggers inside an always-on daemon. The daemon could not work here: a LaunchAgent lives in the
user's GUI domain, so it exists only while logged in and was never alive at 03:00-05:00 to fire
anything. It produced no backup in the nine days it ran. launchd coalesces a fire missed during
sleep into a single run at login/wake, which is the catch-up APScheduler's in-memory job store
could never give (PROGRESS Decisions 2026-09-11 maintenance-to-launchd).

Wiring only — each job composes an existing use-case entry point, and each is safe to run late
or twice, which is what makes the coalesced catch-up sound.
"""

import argparse
import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from beacon.adapters.persistence.backup import backup_database
from beacon.config import Settings
from beacon.ingest import run_probe
from beacon.logging_setup import configure_cli_logging
from beacon.refresh import run_refresh, run_refresh_if_needed

logger = logging.getLogger(__name__)

Job = Callable[[Settings], int]


def _refresh_registries(settings: Settings) -> int:
    return run_refresh(settings)


def _refresh_registries_if_needed(settings: Settings) -> int:
    """Launch-time variant: ingest a snapshot that has never been read, or has gone stale.

    The monthly agent is the wrong cadence for a register that has never been ingested at all —
    UK/NL/US sat that way for sixteen slices. run.sh calls this before serving, so a file
    dropped into data/registries/ is picked up on the next start rather than on the 1st.
    """
    return run_refresh_if_needed(settings)


def _backup(settings: Settings) -> int:
    dest = backup_database(settings.db_path, settings.backups_dir, datetime.now(UTC))
    logger.info("backup_written path=%s", dest)
    return 0


def _probe(settings: Settings) -> int:
    return asyncio.run(run_probe(settings))


JOBS: Mapping[str, Job] = {
    "refresh-registries": _refresh_registries,
    "refresh-registries-if-needed": _refresh_registries_if_needed,
    "backup": _backup,
    "probe": _probe,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one unattended maintenance job.")
    parser.add_argument("job", choices=sorted(JOBS), help="which maintenance job to run")
    args = parser.parse_args(argv)

    configure_cli_logging()
    logger.info("maintenance_start job=%s", args.job)
    exit_code = JOBS[args.job](Settings.from_env())
    logger.info("maintenance_done job=%s exit=%d", args.job, exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
