"""SqliteMatchScoreRepo — caches Tier-1 resume-fit scores (§11 12c).

Dumb repo: the cache policy (what to reuse, what to recompute) lives in the scoring use case.
This just reads/writes rows in job_match_scores keyed (resume_hash, job_canonical_id), storing
the content_hash each score was computed against so the use case can spot a stale posting.
matched/missing skills are stored as JSON arrays (sorted, so the row diffs cleanly).
"""

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime

from beacon.application.ports import CachedScore
from beacon.domain.resume import MatchScore


class SqliteMatchScoreRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_cached(self, resume_hash: str, job_ids: Sequence[int]) -> dict[int, CachedScore]:
        if not job_ids:
            return {}
        placeholders = ",".join("?" * len(job_ids))
        rows = self._conn.execute(
            f"""
            SELECT job_canonical_id, overall, skills_score, level_score, sponsor_score,
                   matched_skills, missing_skills, content_hash
            FROM job_match_scores
            WHERE resume_hash = ? AND job_canonical_id IN ({placeholders})
            """,  # noqa: S608 — placeholders only, values bound
            [resume_hash, *job_ids],
        ).fetchall()
        return {row["job_canonical_id"]: _row_to_cached(row) for row in rows}

    def upsert(
        self,
        resume_hash: str,
        job_id: int,
        content_hash: str,
        score: MatchScore,
        computed_at: datetime,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO job_match_scores (
                resume_hash, job_canonical_id, overall, skills_score, level_score,
                sponsor_score, matched_skills, missing_skills, content_hash, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (resume_hash, job_canonical_id) DO UPDATE SET
                overall = excluded.overall,
                skills_score = excluded.skills_score,
                level_score = excluded.level_score,
                sponsor_score = excluded.sponsor_score,
                matched_skills = excluded.matched_skills,
                missing_skills = excluded.missing_skills,
                content_hash = excluded.content_hash,
                computed_at = excluded.computed_at
            """,
            (
                resume_hash,
                job_id,
                score.overall,
                score.skills_score,
                score.level_score,
                score.sponsor_score,
                json.dumps(sorted(score.matched_skills)),
                json.dumps(sorted(score.missing_skills)),
                content_hash,
                computed_at.isoformat(),
            ),
        )
        self._conn.commit()


def _row_to_cached(row: sqlite3.Row) -> CachedScore:
    return CachedScore(
        score=MatchScore(
            overall=row["overall"],
            skills_score=row["skills_score"],
            level_score=row["level_score"],
            sponsor_score=row["sponsor_score"],
            matched_skills=frozenset(json.loads(row["matched_skills"])),
            missing_skills=frozenset(json.loads(row["missing_skills"])),
        ),
        content_hash=row["content_hash"],
    )
