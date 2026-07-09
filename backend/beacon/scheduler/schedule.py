"""Scheduler wiring (SPEC §9): poll intervals, monthly registry refresh, nightly backup.

Wiring only — each job composes an existing use-case entry point. Cron boundaries are keyed
in LOCAL_TZ (Asia/Jakarta) so "monthly"/"nightly" fall on the local calendar (SPEC §9).
"""

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from beacon.adapters.persistence.backup import backup_database
from beacon.config import LOCAL_TZ, Settings
from beacon.ingest import run_ingest
from beacon.refresh import run_refresh

# SPEC §9 poll cadence. HN's daily-first-week cadence is folded into the 6h boards poll —
# its per-thread unseen-kids cache makes frequent re-polls cheap (slice 7).
POLL_ATS_HOURS = 4
POLL_BOARDS_HOURS = 6


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=LOCAL_TZ)

    async def poll_ats() -> None:
        await run_ingest(settings, poll_boards=False)

    async def poll_boards() -> None:
        await run_ingest(settings, poll_ats=False)

    def refresh_registries() -> None:
        run_refresh(settings)

    def nightly_backup() -> None:
        backup_database(settings.db_path, settings.backups_dir, datetime.now(UTC))

    scheduler.add_job(poll_ats, IntervalTrigger(hours=POLL_ATS_HOURS), id="poll_ats")
    scheduler.add_job(poll_boards, IntervalTrigger(hours=POLL_BOARDS_HOURS), id="poll_boards")
    scheduler.add_job(
        refresh_registries, CronTrigger(day=1, hour=3, timezone=LOCAL_TZ), id="refresh_registries"
    )
    scheduler.add_job(nightly_backup, CronTrigger(hour=4, timezone=LOCAL_TZ), id="nightly_backup")
    return scheduler
