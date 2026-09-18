"""The maintenance jobs are launchd-fired one-shots, one plist each, so the wiring gets a test
the way deploy/com.beacon.digest.plist does: when each fires, that a fire is one-shot rather
than a daemon, and — the drift guard that matters — that every plist names a job the CLI
actually has. They ran as APScheduler crons inside an always-on daemon until 2026-09-11; see
PROGRESS Decisions (maintenance-to-launchd) for why that could never fire on this box."""

import plistlib
from pathlib import Path
from typing import Any

import pytest

from beacon import maintenance
from beacon.config import Settings

DEPLOY = Path(__file__).parents[3] / "deploy"

# plist filename -> (job argument it passes, the calendar entry launchd fires it on)
PLISTS: dict[str, tuple[str, dict[str, int]]] = {
    "com.beacon.refresh.plist": ("refresh-registries", {"Day": 1, "Hour": 3, "Minute": 0}),
    "com.beacon.backup.plist": ("backup", {"Hour": 4, "Minute": 0}),
    "com.beacon.probe.plist": ("probe", {"Weekday": 1, "Hour": 5, "Minute": 0}),
}


def load_plist(name: str) -> dict[str, Any]:
    plist: dict[str, Any] = plistlib.loads((DEPLOY / name).read_bytes())
    return plist


def make_settings() -> Settings:
    return Settings(db_path=Path("beacon.db"), seeds_path=Path("seeds.csv"))


def test_the_cli_offers_exactly_the_maintenance_jobs_the_deploy_agents_call() -> None:
    """Three are launchd-fired; refresh-registries-if-needed is run.sh's launch-time check,
    which is deliberately off the monthly schedule and has no plist of its own."""
    assert set(maintenance.JOBS) == {
        "refresh-registries",
        "refresh-registries-if-needed",
        "backup",
        "probe",
    }


def recording_jobs(called: list[str]) -> dict[str, maintenance.Job]:
    """A stand-in JOBS table whose handlers record that they ran instead of doing the work."""

    def record(name: str) -> maintenance.Job:
        def run(_settings: Settings) -> int:
            called.append(name)
            return 0

        return run

    return {name: record(name) for name in maintenance.JOBS}


@pytest.mark.parametrize("job", sorted(PLISTS[name][0] for name in PLISTS))
def test_running_a_job_calls_its_handler(job: str, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(maintenance, "JOBS", recording_jobs(called))
    monkeypatch.setattr(Settings, "from_env", staticmethod(make_settings))

    exit_code = maintenance.main([job])

    assert (called, exit_code) == ([job], 0)


def test_an_unknown_job_is_rejected_rather_than_silently_skipped() -> None:
    with pytest.raises(SystemExit) as excinfo:
        maintenance.main(["vacuum"])

    assert excinfo.value.code != 0


@pytest.mark.parametrize("name", sorted(PLISTS))
def test_every_plist_names_a_job_the_cli_has(name: str) -> None:
    """The drift guard: a renamed job that leaves a plist behind fails here, not at 04:00."""
    argv: list[str] = load_plist(name)["ProgramArguments"]

    assert PLISTS[name][0] in argv
    assert argv[-1] in maintenance.JOBS


@pytest.mark.parametrize("name", sorted(PLISTS))
def test_every_plist_fires_on_its_maintenance_schedule(name: str) -> None:
    entries: list[dict[str, int]] = load_plist(name)["StartCalendarInterval"]

    assert entries == [PLISTS[name][1]]


@pytest.mark.parametrize("name", sorted(PLISTS))
def test_a_maintenance_fire_is_one_shot_not_a_daemon(name: str) -> None:
    plist = load_plist(name)

    assert not plist.get("KeepAlive")
    assert not plist.get("RunAtLoad")
