"""The hourly digest window is hand-edited XML (deploy/com.beacon.digest.plist), so it gets a
test like any other wiring: when it fires, and that a fire is one-shot rather than a daemon."""

import plistlib
from pathlib import Path
from typing import Any

PLIST = Path(__file__).parents[3] / "deploy" / "com.beacon.digest.plist"
WORKING_HOURS = range(9, 17)  # 09:30 … 16:30 local, eight fires (SPEC §9)


def load_plist() -> dict[str, Any]:
    plist: dict[str, Any] = plistlib.loads(PLIST.read_bytes())
    return plist


def test_fires_at_half_past_every_working_hour() -> None:
    entries: list[dict[str, int]] = load_plist()["StartCalendarInterval"]

    assert {(entry["Hour"], entry["Minute"]) for entry in entries} == {
        (hour, 30) for hour in WORKING_HOURS
    }


def test_a_fire_is_one_shot_not_a_daemon() -> None:
    plist = load_plist()

    assert not plist.get("KeepAlive")
    assert not plist.get("RunAtLoad")
