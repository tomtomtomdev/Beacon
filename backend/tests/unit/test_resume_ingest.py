"""ingest_resume use case (§11 12b): parse → profile → store, active-singleton, hash dedup.

The dedup + activation policy lives in the use case (the repo stays dumb), so these pin it
against an in-memory FakeResumeRepo and the real zero-dep parser.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from beacon.adapters.resume.plaintext import PlainTextResumeParser
from beacon.application.resumes import ingest_resume
from beacon.domain.resume import Resume, ResumeProfile, build_profile

NOW = datetime(2026, 7, 15, tzinfo=UTC)


class FakeResumeRepo:
    """In-memory ResumeRepo implementing the real protocol (fakes over mocks)."""

    def __init__(self) -> None:
        self._rows: list[Resume] = []
        self._next_id = 1

    def insert(self, resume: Resume) -> Resume:
        stored = replace(resume, id=self._next_id)
        self._next_id += 1
        self._rows.append(stored)
        return stored

    def get(self, resume_id: int) -> Resume | None:
        return next((r for r in self._rows if r.id == resume_id), None)

    def get_by_hash(self, resume_hash: str) -> Resume | None:
        return next((r for r in self._rows if r.resume_hash == resume_hash), None)

    def get_active(self) -> Resume | None:
        return next((r for r in self._rows if r.active), None)

    def list_all(self) -> list[Resume]:
        return list(self._rows)

    def set_active(self, resume_id: int) -> bool:
        if not any(r.id == resume_id for r in self._rows):
            return False
        self._rows = [replace(r, active=(r.id == resume_id)) for r in self._rows]
        return True

    def delete(self, resume_id: int) -> bool:
        before = len(self._rows)
        self._rows = [r for r in self._rows if r.id != resume_id]
        return len(self._rows) < before


def test_ingest_resume_stores_profile_and_marks_active() -> None:
    repo = FakeResumeRepo()

    resume = ingest_resume(
        repo,
        PlainTextResumeParser(),
        data="Senior iOS Engineer, 8 years Swift and SwiftUI",
        kind="text",
        label="My CV",
        created_at=NOW,
    )

    assert resume.active is True
    assert resume.profile.level.value == "senior"
    assert {"swift", "swiftui"} <= resume.profile.skills
    assert repo.get_active() == resume


def test_new_active_resume_demotes_the_previous_one() -> None:
    repo = FakeResumeRepo()
    first = ingest_resume(
        repo,
        PlainTextResumeParser(),
        data="Backend engineer, Django",
        kind="text",
        label="A",
        created_at=NOW,
    )

    second = ingest_resume(
        repo,
        PlainTextResumeParser(),
        data="Frontend engineer, React",
        kind="text",
        label="B",
        created_at=NOW,
    )

    assert repo.get_active() == second
    first_id = first.id
    assert first_id is not None
    demoted = repo.get(first_id)
    assert demoted is not None
    assert demoted.active is False


def test_reuploading_identical_text_reuses_row_without_reprofiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeResumeRepo()
    calls = 0

    def counting_build_profile(
        text: str, *, target_countries: frozenset[str] = frozenset()
    ) -> ResumeProfile:
        nonlocal calls
        calls += 1
        return build_profile(text, target_countries=target_countries)

    monkeypatch.setattr("beacon.application.resumes.build_profile", counting_build_profile)

    first = ingest_resume(
        repo,
        PlainTextResumeParser(),
        data="iOS Swift resume",
        kind="text",
        label="CV",
        created_at=NOW,
    )
    second = ingest_resume(
        repo,
        PlainTextResumeParser(),
        data="iOS Swift resume",
        kind="text",
        label="CV",
        created_at=NOW,
    )

    assert first.id == second.id  # same row reused
    assert len(repo.list_all()) == 1
    assert second.active is True
    assert calls == 1  # profiled once; the re-upload did not re-profile
