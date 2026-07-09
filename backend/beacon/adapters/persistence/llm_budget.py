"""SqliteLLMBudget — the hard monthly cap on LLM classifier calls (SPEC §9 cost control).

Implements the LLMBudget port over the llm_usage table (one row per month). The month is
keyed in LOCAL_TZ so the budget resets on the local month boundary, matching the day-boundary
rule the digest uses. The clock is injected so tests are deterministic.
"""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from beacon.config import LOCAL_TZ


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SqliteLLMBudget:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        cap: int,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._conn = conn
        self._cap = cap
        self._clock = clock

    def try_reserve(self) -> bool:
        month = self._month()
        if self.calls_this_month() >= self._cap:
            return False
        self._conn.execute(
            "INSERT INTO llm_usage (month, call_count) VALUES (?, 1)"
            " ON CONFLICT(month) DO UPDATE SET call_count = call_count + 1",
            (month,),
        )
        self._conn.commit()
        return True

    def calls_this_month(self) -> int:
        """LLM calls reserved so far this (local) month — for reporting/acceptance, not the
        gate. Zero when the month has no row yet."""
        row = self._conn.execute(
            "SELECT call_count FROM llm_usage WHERE month = ?", (self._month(),)
        ).fetchone()
        return int(row["call_count"]) if row is not None else 0

    def _month(self) -> str:
        return self._clock().astimezone(LOCAL_TZ).strftime("%Y-%m")
