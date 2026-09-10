"""The scheduler wires the SPEC §9 maintenance crons. Polling is not among them: it fires
from the hourly launchd window (deploy/com.beacon.digest.plist), not from this process."""

from pathlib import Path

from beacon.config import Settings
from beacon.scheduler.schedule import build_scheduler


def make_settings() -> Settings:
    return Settings(db_path=Path("beacon.db"), seeds_path=Path("seeds.csv"))


def test_registers_the_refresh_backup_and_probe_jobs_and_no_polls() -> None:
    scheduler = build_scheduler(make_settings())

    assert {job.id for job in scheduler.get_jobs()} == {
        "refresh_registries",
        "nightly_backup",
        "probe_quarantined",
    }
