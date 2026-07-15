"""Resume ingest use case (§11 12b): parse → profile → store.

The dedup + active-singleton policy lives here (the repo stays dumb): identical text (same
resume_hash) reuses the stored row and is not re-profiled; a new resume is profiled once,
inserted, and made the sole active one, demoting whatever was active before.
"""

from dataclasses import replace
from datetime import datetime

from beacon.application.ports import ResumeParser, ResumeRepo
from beacon.domain.resume import Resume, build_profile, resume_hash


def ingest_resume(
    repo: ResumeRepo,
    parser: ResumeParser,
    *,
    data: bytes | str,
    kind: str,
    label: str,
    target_countries: frozenset[str] = frozenset(),
    created_at: datetime,
) -> Resume:
    text = parser.parse(data, kind)
    digest = resume_hash(text)

    existing = repo.get_by_hash(digest)
    if existing is not None:
        existing_id = existing.id
        assert existing_id is not None  # noqa: S101 — a persisted resume always has an id
        repo.set_active(existing_id)
        return replace(existing, active=True)

    profile = build_profile(text, target_countries=target_countries)
    inserted = repo.insert(
        Resume(
            id=None,
            label=label,
            source_text=text,
            profile=profile,
            resume_hash=digest,
            active=True,
            created_at=created_at,
        )
    )
    inserted_id = inserted.id
    assert inserted_id is not None  # noqa: S101 — insert always assigns an id
    repo.set_active(inserted_id)
    return replace(inserted, active=True)
