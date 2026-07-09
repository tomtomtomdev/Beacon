"""The scheduler wires the SPEC §9 poll/refresh/backup jobs onto their intervals."""

from datetime import timedelta
from pathlib import Path

from apscheduler.triggers.interval import IntervalTrigger

from beacon.config import Settings
from beacon.scheduler.schedule import build_scheduler


def make_settings() -> Settings:
    return Settings(db_path=Path("beacon.db"), seeds_path=Path("seeds.csv"))


def test_registers_the_poll_refresh_and_backup_jobs() -> None:
    scheduler = build_scheduler(make_settings())

    assert {job.id for job in scheduler.get_jobs()} == {
        "poll_ats",
        "poll_boards",
        "refresh_registries",
        "nightly_backup",
    }


def test_ats_and_boards_poll_on_their_spec_intervals() -> None:
    by_id = {job.id: job for job in build_scheduler(make_settings()).get_jobs()}

    ats_trigger = by_id["poll_ats"].trigger
    boards_trigger = by_id["poll_boards"].trigger
    assert isinstance(ats_trigger, IntervalTrigger) and ats_trigger.interval == timedelta(hours=4)
    assert isinstance(boards_trigger, IntervalTrigger)
    assert boards_trigger.interval == timedelta(hours=6)
