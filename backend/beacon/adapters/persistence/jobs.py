import sqlite3
from datetime import datetime

from beacon.domain.job import NormalizedJob


class SqliteJobRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, company_id: int, job: NormalizedJob, seen_at: datetime) -> None:
        self._conn.execute(
            """
            INSERT INTO jobs (
                company_id, source_id, external_id, title, description, url,
                location_raw, country, city, content_hash, posted_at,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_id, external_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                url = excluded.url,
                location_raw = excluded.location_raw,
                country = excluded.country,
                city = excluded.city,
                content_hash = excluded.content_hash,
                posted_at = excluded.posted_at,
                last_seen_at = excluded.last_seen_at
            """,
            (
                company_id,
                job.source_id,
                job.external_id,
                job.title,
                job.description,
                job.url,
                job.location_raw,
                job.country,
                job.city,
                job.content_hash,
                job.posted_at.isoformat() if job.posted_at else None,
                seen_at.isoformat(),
                seen_at.isoformat(),
            ),
        )
        self._conn.commit()
