"""SqliteCountryRepo — the visa reference table (SPEC §4), seeded from COUNTRY_REFERENCE."""

import sqlite3
from collections.abc import Sequence
from datetime import date

from beacon.domain.visa import CountryReference, PriorityTier

_COLUMNS = (
    "code, name, visa_summary, pr_summary, citizenship_summary,"
    " registry_name, priority_tier, verified_at, source_url"
)


class SqliteCountryRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_all(self) -> list[CountryReference]:
        # Primary target countries first (SPEC §3), then alphabetical within tier.
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM countries"
            " ORDER BY CASE priority_tier WHEN 'primary' THEN 0 ELSE 1 END, name"
        )
        return [self._to_reference(row) for row in rows]

    def seed(self, countries: Sequence[CountryReference]) -> None:
        self._conn.executemany(
            f"INSERT INTO countries ({_COLUMNS})"
            " VALUES (:code, :name, :visa_summary, :pr_summary, :citizenship_summary,"
            " :registry_name, :priority_tier, :verified_at, :source_url)"
            " ON CONFLICT(code) DO UPDATE SET"
            " name = excluded.name, visa_summary = excluded.visa_summary,"
            " pr_summary = excluded.pr_summary, citizenship_summary = excluded.citizenship_summary,"
            " registry_name = excluded.registry_name, priority_tier = excluded.priority_tier,"
            " verified_at = excluded.verified_at, source_url = excluded.source_url",
            [self._to_params(c) for c in countries],
        )
        self._conn.commit()

    @staticmethod
    def _to_params(c: CountryReference) -> dict[str, str]:
        return {
            "code": c.code,
            "name": c.name,
            "visa_summary": c.visa_summary,
            "pr_summary": c.pr_summary,
            "citizenship_summary": c.citizenship_summary,
            "registry_name": c.registry_name,
            "priority_tier": c.priority_tier.value,
            "verified_at": c.verified_at.isoformat(),
            "source_url": c.source_url,
        }

    @staticmethod
    def _to_reference(row: sqlite3.Row) -> CountryReference:
        return CountryReference(
            code=row["code"],
            name=row["name"],
            visa_summary=row["visa_summary"],
            pr_summary=row["pr_summary"],
            citizenship_summary=row["citizenship_summary"],
            registry_name=row["registry_name"],
            priority_tier=PriorityTier(row["priority_tier"]),
            verified_at=date.fromisoformat(row["verified_at"]),
            source_url=row["source_url"],
        )
