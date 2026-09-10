"""Scheduler wiring (SPEC §9): monthly registry refresh, nightly backup, weekly restore probe.

Wiring only — each job composes an existing use-case entry point. Cron boundaries are keyed
in LOCAL_TZ (Asia/Jakarta) so "monthly"/"nightly" fall on the local calendar (SPEC §9).

Polling is deliberately absent: it fires from launchd instead, on the hour at :30 between
09:30 and 16:30 local, so a digest lands inside working hours rather than overnight
(deploy/com.beacon.digest.plist; PROGRESS Decisions 2026-09-10). This process keeps only the
jobs that must run unattended around the clock.
"""

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from beacon.adapters.persistence.backup import backup_database
from beacon.config import LOCAL_TZ, Settings
from beacon.ingest import run_probe
from beacon.refresh import run_refresh


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=LOCAL_TZ)

    def refresh_registries() -> None:
        run_refresh(settings)

    def nightly_backup() -> None:
        backup_database(settings.db_path, settings.backups_dir, datetime.now(UTC))

    async def probe_quarantined() -> None:
        await run_probe(settings)

    scheduler.add_job(
        refresh_registries, CronTrigger(day=1, hour=3, timezone=LOCAL_TZ), id="refresh_registries"
    )
    scheduler.add_job(nightly_backup, CronTrigger(hour=4, timezone=LOCAL_TZ), id="nightly_backup")
    # Weekly restore probe: retry quarantined sources so a temporary outage self-heals (SPEC §7).
    scheduler.add_job(
        probe_quarantined,
        CronTrigger(day_of_week="mon", hour=5, timezone=LOCAL_TZ),
        id="probe_quarantined",
    )
    return scheduler
