"""The digest window is hand-edited XML (deploy/com.beacon.digest.plist), so it gets a test
like any other wiring: when it fires, that two fires can never collide, and that a fire is
one-shot rather than a daemon."""

import plistlib
from itertools import pairwise
from pathlib import Path
from typing import Any

PLIST = Path(__file__).parents[3] / "deploy" / "com.beacon.digest.plist"

# Three fires a day, local time (SPEC §9, narrowed from eight on 2026-09-11): a full poll of
# the pollable seeds at 1 rps runs 30-45 min, so :30-past-every-working-hour spent most of the
# day polling and leaned on the lock to skip collisions.
FIRES = {(8, 0), (12, 0), (16, 30)}

# deploy/hourly-digest.sh caps a run at BEACON_HOURLY_TIMEOUT, default 3000s.
WATCHDOG_MINUTES = 50


def load_plist() -> dict[str, Any]:
    plist: dict[str, Any] = plistlib.loads(PLIST.read_bytes())
    return plist


def fire_minutes() -> list[int]:
    entries: list[dict[str, int]] = load_plist()["StartCalendarInterval"]
    return sorted(entry["Hour"] * 60 + entry["Minute"] for entry in entries)


def test_fires_three_times_a_day() -> None:
    entries: list[dict[str, int]] = load_plist()["StartCalendarInterval"]

    assert {(entry["Hour"], entry["Minute"]) for entry in entries} == FIRES


def test_no_fire_can_meet_the_previous_one_still_running() -> None:
    """A run held to the watchdog must still end before the next fire. Closer than that and
    the lock in hourly-digest.sh starts skipping fires instead of guarding against crashes."""
    gaps = [later - earlier for earlier, later in pairwise(fire_minutes())]

    assert min(gaps) > WATCHDOG_MINUTES


def test_a_fire_is_one_shot_not_a_daemon() -> None:
    plist = load_plist()

    assert not plist.get("KeepAlive")
    assert not plist.get("RunAtLoad")
