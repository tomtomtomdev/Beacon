"""SqliteLLMBudget: the hard monthly cap on LLM calls, against a real migrated DB.

The clock is injected so month boundaries are deterministic (no waiting, no wall clock).
Months are keyed in LOCAL_TZ (Asia/Jakarta), so a late-UTC instant counts toward the local
month — same day-boundary rule the digest will use (SPEC §9).
"""

import sqlite3
from datetime import UTC, datetime

from beacon.adapters.persistence.llm_budget import SqliteLLMBudget


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_reserves_until_the_monthly_cap_then_refuses(db: sqlite3.Connection) -> None:
    clock = FakeClock(datetime(2026, 7, 9, 5, 0, tzinfo=UTC))
    budget = SqliteLLMBudget(db, cap=3, clock=clock)

    assert [budget.try_reserve() for _ in range(4)] == [True, True, True, False]
    stored = db.execute("SELECT call_count FROM llm_usage WHERE month = '2026-07'").fetchone()
    assert stored["call_count"] == 3  # the refused 4th attempt was not counted


def test_a_new_month_resets_the_budget(db: sqlite3.Connection) -> None:
    clock = FakeClock(datetime(2026, 7, 9, 5, 0, tzinfo=UTC))
    budget = SqliteLLMBudget(db, cap=1, clock=clock)

    assert budget.try_reserve() is True
    assert budget.try_reserve() is False  # July is spent

    clock.now = datetime(2026, 8, 1, 5, 0, tzinfo=UTC)
    assert budget.try_reserve() is True  # August has its own allowance


def test_month_key_uses_local_time_not_utc(db: sqlite3.Connection) -> None:
    # 2026-07-31 20:00 UTC is 2026-08-01 03:00 in Asia/Jakarta (UTC+7) — an August call.
    clock = FakeClock(datetime(2026, 7, 31, 20, 0, tzinfo=UTC))
    budget = SqliteLLMBudget(db, cap=5, clock=clock)

    budget.try_reserve()

    assert db.execute("SELECT month FROM llm_usage").fetchone()["month"] == "2026-08"
