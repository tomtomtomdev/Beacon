import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from beacon.application.ports import (
    DuplicateSource,
    JobDetail,
    JobFilters,
    JobListing,
    JobPage,
    JobScoringInput,
)
from beacon.domain.classification import Classification, format_categories
from beacon.domain.dedup import DedupRow
from beacon.domain.job import NormalizedJob
from beacon.domain.registry import registry_names
from beacon.domain.sponsorship import SORT_RANK, SponsorSignal, SponsorTier
from beacon.domain.status import UserStatus

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
        # Duplicates hang off their canonical via canonical_id; the list shows canonicals only.
        clauses: list[str] = ["jobs.canonical_id IS NULL"]
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
        if filters.status is None:
            clauses.append(f"jobs.user_status != '{UserStatus.HIDDEN.value}'")
        elif filters.status != "all":
            clauses.append("jobs.user_status = ?")
            params.append(filters.status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        # sort=match orders by the cached fit score (a LEFT JOIN so uncached jobs still appear,
        # sorted last); the application re-sorts the returned window by the fresh score, so this
        # join only biases which rows land in the window as the cache warms across page visits.
        join = ""
        join_params: list[str] = []
        if filters.sort == "match" and filters.resume_hash is not None:
            join = (
                "LEFT JOIN job_match_scores ms"
                " ON ms.job_canonical_id = jobs.id AND ms.resume_hash = ?"
            )
            join_params.append(filters.resume_hash)
            order_by = (
                f"ms.overall IS NULL, ms.overall DESC, {_SORT_RANK_CASE} DESC, jobs.posted_at DESC"
            )
        elif filters.sort == "date":
            # "date" ignores tier — pure recency.
            order_by = "jobs.posted_at DESC"
        else:
            # the default keeps likely sponsors on top (posted_at breaks ties).
            order_by = f"{_SORT_RANK_CASE} DESC, jobs.posted_at DESC"

        total = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM jobs {where}",
            params,  # noqa: S608 — params bound
        ).fetchone()["n"]
        rows = self._conn.execute(
            f"""
            SELECT jobs.id, jobs.title, companies.name AS company, jobs.url,
                   jobs.location_raw, jobs.country, jobs.city, jobs.categories,
                   jobs.level, jobs.posted_at, jobs.sponsor_tier, jobs.user_status
            FROM jobs JOIN companies ON companies.id = jobs.company_id
            {join}
            {where}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*join_params, *params, str(filters.limit), str(filters.offset)],
        ).fetchall()
        return JobPage(jobs=[_row_to_listing(row) for row in rows], total=total)

    def get_scoring_inputs(self, job_ids: Sequence[int]) -> dict[int, JobScoringInput]:
        if not job_ids:
            return {}
        placeholders = ",".join("?" * len(job_ids))
        rows = self._conn.execute(
            f"SELECT id, content_hash, description FROM jobs WHERE id IN ({placeholders})",  # noqa: S608 — placeholders only
            list(job_ids),
        ).fetchall()
        return {
            row["id"]: JobScoringInput(
                content_hash=row["content_hash"], description=row["description"]
            )
            for row in rows
        }

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

    def list_ambiguous(self) -> list[tuple[int, NormalizedJob]]:
        rows = self._conn.execute(
            """
            SELECT id, source_id, external_id, title, url, description, location_raw,
                   country, city, posted_at, content_hash
            FROM jobs WHERE categories = ''
            """
        ).fetchall()
        return [(row["id"], _row_to_normalized(row)) for row in rows]

    def set_classification(self, job_id: int, classification: Classification) -> None:
        self._conn.execute(
            "UPDATE jobs SET categories = ?, level = ? WHERE id = ?",
            (format_categories(classification.categories), classification.level.value, job_id),
        )
        self._conn.commit()

    def list_dedup_rows(self) -> list[DedupRow]:
        rows = self._conn.execute(
            "SELECT id, company_id, title, country, description FROM jobs"
        ).fetchall()
        return [
            DedupRow(
                id=row["id"],
                company_id=row["company_id"],
                title=row["title"],
                country=row["country"],
                description=row["description"],
            )
            for row in rows
        ]

    def set_canonical_links(self, links: Mapping[int, int | None]) -> None:
        self._conn.executemany(
            "UPDATE jobs SET canonical_id = ? WHERE id = ?",
            [(canonical_id, job_id) for job_id, canonical_id in links.items()],
        )
        self._conn.commit()

    def set_user_status(self, job_id: int, status: str) -> int | None:
        row = self._conn.execute(
            "SELECT id, canonical_id FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        # Status lives on the canonical row (the one the list shows); a duplicate id lands there.
        canonical_id: int = row["canonical_id"] if row["canonical_id"] is not None else row["id"]
        self._conn.execute("UPDATE jobs SET user_status = ? WHERE id = ?", (status, canonical_id))
        self._conn.commit()
        return canonical_id

    def get_job_detail(self, job_id: int) -> JobDetail | None:
        row = self._conn.execute(
            "SELECT id, canonical_id FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        canonical_id = row["canonical_id"] if row["canonical_id"] is not None else row["id"]

        job = self._conn.execute(
            """
            SELECT jobs.id, jobs.title, companies.name AS company, jobs.url, jobs.description,
                   jobs.location_raw, jobs.country, jobs.city, jobs.categories, jobs.level,
                   jobs.posted_at, jobs.sponsor_tier, jobs.sponsor_evidence, jobs.user_status,
                   companies.registry_flags, companies.match_confidence
            FROM jobs JOIN companies ON companies.id = jobs.company_id
            WHERE jobs.id = ?
            """,
            (canonical_id,),
        ).fetchone()

        sources = self._conn.execute(
            """
            SELECT jobs.source_id AS source, companies.name AS company, jobs.url
            FROM jobs JOIN companies ON companies.id = jobs.company_id
            WHERE jobs.id = ? OR jobs.canonical_id = ?
            ORDER BY jobs.id
            """,
            (canonical_id, canonical_id),
        ).fetchall()

        categories = job["categories"]
        posted_at = job["posted_at"]
        return JobDetail(
            id=job["id"],
            title=job["title"],
            company=job["company"],
            url=job["url"],
            description=job["description"],
            location_raw=job["location_raw"],
            country=job["country"],
            city=job["city"],
            categories=tuple(categories.split(",")) if categories else (),
            level=job["level"],
            posted_at=datetime.fromisoformat(posted_at) if posted_at else None,
            sponsor_tier=job["sponsor_tier"],
            sponsor_evidence=job["sponsor_evidence"],
            registries=registry_names(job["registry_flags"]),
            match_confidence=job["match_confidence"],
            user_status=job["user_status"],
            duplicate_sources=tuple(
                DuplicateSource(source=s["source"], company=s["company"], url=s["url"])
                for s in sources
            ),
        )

    def sweep_absent_jobs(
        self,
        source_id: str,
        company_id: int | None,
        seen_external_ids: set[str],
        now: datetime,
        *,
        threshold: int,
    ) -> int:
        scope = "source_id = ?"
        scope_params: list[object] = [source_id]
        if company_id is not None:
            scope += " AND company_id = ?"
            scope_params.append(company_id)

        seen = list(seen_external_ids)
        placeholders = ",".join("?" * len(seen))
        absent = f"{scope} AND external_id NOT IN ({placeholders})" if seen else scope
        absent_params = [*scope_params, *seen]

        # Count jobs that this sweep will newly close (absent, still open, reaching threshold).
        newly_closed: int = self._conn.execute(
            f"SELECT COUNT(*) FROM jobs"
            f" WHERE {absent} AND closed_at IS NULL AND consecutive_misses + 1 >= ?",
            (*absent_params, threshold),
        ).fetchone()[0]

        # Present again → reset misses and reopen (a closed posting that reappears is live).
        if seen:
            self._conn.execute(
                f"UPDATE jobs SET consecutive_misses = 0, closed_at = NULL"
                f" WHERE {scope} AND external_id IN ({placeholders})",
                (*scope_params, *seen),
            )
        # Absent → one more miss; close once the counter reaches the threshold.
        self._conn.execute(
            f"UPDATE jobs SET consecutive_misses = consecutive_misses + 1,"
            f" closed_at = CASE WHEN consecutive_misses + 1 >= ? AND closed_at IS NULL"
            f" THEN ? ELSE closed_at END"
            f" WHERE {absent}",
            (threshold, now.isoformat(), *absent_params),
        )
        self._conn.commit()
        return newly_closed

    def upsert(
        self,
        company_id: int,
        job: NormalizedJob,
        seen_at: datetime,
        classification: Classification | None = None,
        sponsorship: SponsorSignal | None = None,
    ) -> None:
        # categories/level and sponsor_tier/evidence are only rewritten when a fresh
        # classification / sponsorship signal is supplied. On an unchanged re-poll both are
        # None and the stored values survive (see ingest caching): categories via COALESCE,
        # and sponsor_* keyed off :sponsor_tier being NULL (so a registry-derived tier,
        # written later by refresh_registries, is never clobbered back to 'unknown').
        self._conn.execute(
            """
            INSERT INTO jobs (
                company_id, source_id, external_id, title, description, url,
                location_raw, country, city, categories, level,
                sponsor_tier, sponsor_evidence, content_hash, posted_at,
                first_seen_at, last_seen_at
            ) VALUES (
                :company_id, :source_id, :external_id, :title, :description, :url,
                :location_raw, :country, :city, :categories, :level,
                COALESCE(:sponsor_tier, 'unknown'), :sponsor_evidence, :content_hash,
                :posted_at, :seen_at, :seen_at
            )
            ON CONFLICT (source_id, external_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                url = excluded.url,
                location_raw = excluded.location_raw,
                country = excluded.country,
                city = excluded.city,
                categories = COALESCE(excluded.categories, jobs.categories),
                level = COALESCE(excluded.level, jobs.level),
                sponsor_tier = COALESCE(:sponsor_tier, jobs.sponsor_tier),
                sponsor_evidence = CASE
                    WHEN :sponsor_tier IS NOT NULL THEN :sponsor_evidence
                    ELSE jobs.sponsor_evidence
                END,
                content_hash = excluded.content_hash,
                posted_at = excluded.posted_at,
                last_seen_at = excluded.last_seen_at,
                -- A materially edited posting (changed hash) is new again; an
                -- unchanged re-poll keeps the user's seen/hidden/starred decision.
                user_status = CASE
                    WHEN jobs.content_hash != excluded.content_hash THEN 'new'
                    ELSE jobs.user_status
                END
            """,
            {
                "company_id": company_id,
                "source_id": job.source_id,
                "external_id": job.external_id,
                "title": job.title,
                "description": job.description,
                "url": job.url,
                "location_raw": job.location_raw,
                "country": job.country,
                "city": job.city,
                "categories": (
                    format_categories(classification.categories) if classification else None
                ),
                "level": classification.level.value if classification else None,
                "sponsor_tier": sponsorship.tier.value if sponsorship else None,
                "sponsor_evidence": sponsorship.evidence if sponsorship else None,
                "content_hash": job.content_hash,
                "posted_at": job.posted_at.isoformat() if job.posted_at else None,
                "seen_at": seen_at.isoformat(),
            },
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
        user_status=row["user_status"],
    )
