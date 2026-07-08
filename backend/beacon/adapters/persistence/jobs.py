import sqlite3
from datetime import UTC, datetime

from beacon.application.ports import JobFilters, JobListing, JobPage
from beacon.domain.classification import Classification, format_categories
from beacon.domain.job import NormalizedJob
from beacon.domain.sponsorship import SORT_RANK, SponsorTier

# Built from the domain table so SQL can never disagree with it.
_SORT_RANK_CASE = (
    "CASE jobs.sponsor_tier "
    + " ".join(f"WHEN '{tier.value}' THEN {rank}" for tier, rank in SORT_RANK.items())
    + " ELSE 0 END"
)

# Explicit-text tiers win over the registry signal, so registry re-resolution skips them.
_EXPLICIT_TIERS = (SponsorTier.EXPLICIT_YES, SponsorTier.EXPLICIT_NO)
_EXPLICIT_TIER_LITERALS = ", ".join(f"'{tier.value}'" for tier in _EXPLICIT_TIERS)


class SqliteJobRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def search(self, filters: JobFilters) -> JobPage:
        clauses: list[str] = []
        params: list[str] = []
        if filters.q:
            clauses.append("(jobs.title LIKE ? OR jobs.description LIKE ?)")
            params += [f"%{filters.q}%"] * 2
        if filters.countries:
            placeholders = ", ".join("?" * len(filters.countries))
            clauses.append(f"jobs.country IN ({placeholders})")
            params += list(filters.countries)
        if filters.categories:
            # categories is a comma-joined multi-label string; match on comma-delimited
            # membership so a filter for "ios" hits "ai-ml,ios" but never a substring.
            ors = " OR ".join("(',' || jobs.categories || ',') LIKE ?" for _ in filters.categories)
            clauses.append(f"({ors})")
            params += [f"%,{category},%" for category in filters.categories]
        if filters.levels:
            placeholders = ", ".join("?" * len(filters.levels))
            clauses.append(f"jobs.level IN ({placeholders})")
            params += list(filters.levels)
        if filters.posted_since is not None:
            clauses.append("jobs.posted_at >= ?")
            params.append(filters.posted_since.astimezone(UTC).isoformat())
        if filters.sponsor_tiers:
            placeholders = ", ".join("?" * len(filters.sponsor_tiers))
            clauses.append(f"jobs.sponsor_tier IN ({placeholders})")
            params += list(filters.sponsor_tiers)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        # "date" ignores tier; the default keeps likely sponsors on top (posted_at breaks ties).
        order_by = (
            "jobs.posted_at DESC"
            if filters.sort == "date"
            else f"{_SORT_RANK_CASE} DESC, jobs.posted_at DESC"
        )

        total = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM jobs {where}",
            params,  # noqa: S608 — params bound
        ).fetchone()["n"]
        rows = self._conn.execute(
            f"""
            SELECT jobs.id, jobs.title, companies.name AS company, jobs.url,
                   jobs.location_raw, jobs.country, jobs.city, jobs.categories,
                   jobs.level, jobs.posted_at, jobs.sponsor_tier
            FROM jobs JOIN companies ON companies.id = jobs.company_id
            {where}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, str(filters.limit), str(filters.offset)],
        ).fetchall()
        return JobPage(jobs=[_row_to_listing(row) for row in rows], total=total)

    def resolve_registry_tier(self, company_id: int, tier: str) -> None:
        self._conn.execute(
            f"UPDATE jobs SET sponsor_tier = ?"  # noqa: S608 — literals are enum values
            f" WHERE company_id = ? AND sponsor_tier NOT IN ({_EXPLICIT_TIER_LITERALS})",
            (tier, company_id),
        )
        self._conn.commit()

    def content_hash_for(self, source_id: str, external_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT content_hash FROM jobs WHERE source_id = ? AND external_id = ?",
            (source_id, external_id),
        ).fetchone()
        return row["content_hash"] if row is not None else None

    def list_unclassified(self) -> list[tuple[int, NormalizedJob]]:
        rows = self._conn.execute(
            """
            SELECT id, source_id, external_id, title, url, description, location_raw,
                   country, city, posted_at, content_hash
            FROM jobs WHERE categories IS NULL
            """
        ).fetchall()
        return [(row["id"], _row_to_normalized(row)) for row in rows]

    def set_classification(self, job_id: int, classification: Classification) -> None:
        self._conn.execute(
            "UPDATE jobs SET categories = ?, level = ? WHERE id = ?",
            (format_categories(classification.categories), classification.level.value, job_id),
        )
        self._conn.commit()

    def upsert(
        self,
        company_id: int,
        job: NormalizedJob,
        seen_at: datetime,
        classification: Classification | None = None,
    ) -> None:
        # categories/level are only rewritten when a fresh classification is supplied
        # (COALESCE keeps the prior values on an unchanged re-poll — see ingest caching).
        categories = format_categories(classification.categories) if classification else None
        level = classification.level.value if classification else None
        self._conn.execute(
            """
            INSERT INTO jobs (
                company_id, source_id, external_id, title, description, url,
                location_raw, country, city, categories, level, content_hash, posted_at,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_id, external_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                url = excluded.url,
                location_raw = excluded.location_raw,
                country = excluded.country,
                city = excluded.city,
                categories = COALESCE(excluded.categories, jobs.categories),
                level = COALESCE(excluded.level, jobs.level),
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
                categories,
                level,
                job.content_hash,
                job.posted_at.isoformat() if job.posted_at else None,
                seen_at.isoformat(),
                seen_at.isoformat(),
            ),
        )
        self._conn.commit()


def _row_to_normalized(row: sqlite3.Row) -> NormalizedJob:
    posted_at = row["posted_at"]
    return NormalizedJob(
        source_id=row["source_id"],
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        description=row["description"],
        location_raw=row["location_raw"],
        country=row["country"],
        city=row["city"],
        posted_at=datetime.fromisoformat(posted_at) if posted_at else None,
        content_hash=row["content_hash"],
    )


def _row_to_listing(row: sqlite3.Row) -> JobListing:
    posted_at = row["posted_at"]
    categories = row["categories"]
    return JobListing(
        id=row["id"],
        title=row["title"],
        company=row["company"],
        url=row["url"],
        location_raw=row["location_raw"],
        country=row["country"],
        city=row["city"],
        categories=tuple(categories.split(",")) if categories else (),
        level=row["level"],
        posted_at=datetime.fromisoformat(posted_at) if posted_at else None,
        sponsor_tier=row["sponsor_tier"],
    )
