"""The digest window is hand-edited XML (deploy/com.beacon.digest.plist), so it gets a test
like any other wiring: when it fires, that two fires can never collide, and that a fire is
one-shot rather than a daemon."""

import plistlib
from itertools import pairwise
from pathlib import Path
from typing import Any

PLIST = Path(__file__).parents[3] / "deploy" / "com.beacon.digest.plist"

# One fire a day at 16:00 local time (SPEC §9, narrowed from three on 2026-09-30; from eight
# on 2026-09-11): a full poll of the pollable seeds at 1 rps runs 30-45 min.
FIRES = {(16, 0)}

MINUTES_PER_DAY = 24 * 60

# deploy/hourly-digest.sh caps a run at BEACON_HOURLY_TIMEOUT, default 3000s.
WATCHDOG_MINUTES = 50


def load_plist() -> dict[str, Any]:
    plist: dict[str, Any] = plistlib.loads(PLIST.read_bytes())
    return plist


def fire_minutes() -> list[int]:
    entries: list[dict[str, int]] = load_plist()["StartCalendarInterval"]
    return sorted(entry["Hour"] * 60 + entry["Minute"] for entry in entries)


def test_fires_once_a_day_at_four_pm() -> None:
    entries: list[dict[str, int]] = load_plist()["StartCalendarInterval"]

    assert {(entry["Hour"], entry["Minute"]) for entry in entries} == FIRES


def test_no_fire_can_meet_the_previous_one_still_running() -> None:
    """A run held to the watchdog must still end before the next fire. Closer than that and
    the lock in hourly-digest.sh starts skipping fires instead of guarding against crashes."""
    minutes = fire_minutes()
    # The wrap from the last fire to tomorrow's first is a gap too — the only one for a
    # single daily fire.
    gaps = [
        later - earlier for earlier, later in pairwise([*minutes, minutes[0] + MINUTES_PER_DAY])
    ]

    assert min(gaps) > WATCHDOG_MINUTES


def test_a_fire_is_one_shot_not_a_daemon() -> None:
    plist = load_plist()

    assert not plist.get("KeepAlive")
    assert not plist.get("RunAtLoad")
