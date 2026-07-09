"""registries_meta persistence: when each sponsor-registry snapshot was last ingested.

Written by refresh_registries, read by the digest's staleness nag (SPEC §7: registries never
quarantine — they just warn when a snapshot is older than 45 days)."""

import sqlite3
from datetime import datetime

from beacon.domain.registry import RegistryMeta


class SqliteRegistriesMetaRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record(self, registry: str, fetched_at: datetime, row_count: int) -> None:
        self._conn.execute(
            "INSERT INTO registries_meta (registry, fetched_at, row_count) VALUES (?, ?, ?)"
            " ON CONFLICT (registry) DO UPDATE SET"
            " fetched_at = excluded.fetched_at, row_count = excluded.row_count",
            (registry, fetched_at.isoformat(), row_count),
        )
        self._conn.commit()

    def list_all(self) -> list[RegistryMeta]:
        rows = self._conn.execute(
            "SELECT registry, fetched_at, row_count FROM registries_meta ORDER BY registry"
        ).fetchall()
        return [
            RegistryMeta(
                registry=row["registry"],
                fetched_at=datetime.fromisoformat(row["fetched_at"]),
                row_count=row["row_count"],
            )
            for row in rows
        ]
