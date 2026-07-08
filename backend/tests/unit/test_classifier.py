"""HeuristicClassifier: keyword-driven category (multi-label) + level from title/years.

Table-driven — a spot-check miss becomes a new row here, never a branch in the classifier.
Word-boundary matching is deliberately exercised (go/ml/html traps) because that is the
first thing to break when the keyword tables grow.
"""

from datetime import UTC, datetime

import pytest

from beacon.adapters.classify.heuristic import HeuristicClassifier
from beacon.domain.classification import Category, Level
from beacon.domain.job import NormalizedJob


def _job(title: str, description: str = "") -> NormalizedJob:
    return NormalizedJob(
        source_id="greenhouse:test",
        external_id="1",
        title=title,
        url="https://example.com/1",
        description=description,
        location_raw="Remote",
        country=None,
        city=None,
        posted_at=datetime(2026, 7, 1, tzinfo=UTC),
        content_hash="hash",
    )


CATEGORY_CASES = [
    ("ios-swift", "Senior iOS Engineer", "Swift, SwiftUI and UIKit experience", {Category.IOS}),
    ("android-kotlin", "Android Developer", "Kotlin with Jetpack Compose", {Category.ANDROID}),
    ("flutter-dart", "Mobile Engineer", "Build with Flutter and Dart", {Category.FLUTTER}),
    ("aiml", "ML Engineer", "PyTorch, LLM fine-tuning, RAG, CUDA kernels", {Category.AI_ML}),
    ("backend", "Backend Engineer", "Django, FastAPI, Go and gRPC services", {Category.BACKEND}),
    ("frontend", "Frontend Engineer", "React, Vue and modern CSS", {Category.FRONTEND}),
    ("fullstack", "Full-Stack Engineer", "Comfortable full stack", {Category.FULLSTACK}),
    (
        "multi-ios-aiml",
        "iOS ML Engineer",
        "Ship Swift apps with on-device PyTorch models",
        {Category.IOS, Category.AI_ML},
    ),
    (
        "multi-front-back",
        "Software Engineer",
        "React on the frontend, Django on the backend",
        {Category.FRONTEND, Category.BACKEND},
    ),
    # Word-boundary traps: "go" must not fire on "going/algorithms", "ml" not on "html".
    ("no-go-trap", "Engineer", "We are going to build great algorithms", set()),
    ("no-ml-in-html", "Frontend Engineer", "Hand-write HTML and CSS", {Category.FRONTEND}),
    # Honest empty: nothing technical matched (LLM fallback cleans residue in slice 9).
    ("empty", "Project Manager", "Own the roadmap and stakeholders", set()),
]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [(t, d, e) for _, t, d, e in CATEGORY_CASES],
    ids=[cid for cid, *_ in CATEGORY_CASES],
)
def test_category_classification(title: str, description: str, expected: set[Category]) -> None:
    result = HeuristicClassifier().classify(_job(title, description))

    assert result.categories == frozenset(expected)


LEVEL_CASES = [
    ("senior-title", "Senior iOS Engineer", "", Level.SENIOR),
    ("staff-title", "Staff Software Engineer", "", Level.STAFF),
    ("lead-title", "Lead Backend Engineer", "", Level.LEAD),
    ("principal-title", "Principal Engineer", "", Level.PRINCIPAL),
    ("junior-title", "Junior Developer", "", Level.JUNIOR),
    ("intern-title", "Engineering Intern", "", Level.INTERN),
    ("sr-abbrev", "Sr. Software Engineer", "", Level.SENIOR),
    ("years-to-senior", "Engineer III", "5+ years of experience required", Level.SENIOR),
    ("most-senior-wins", "Senior Staff Engineer", "", Level.STAFF),
    ("bare-unspecified", "Software Engineer", "Join our team", Level.UNSPECIFIED),
]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [(t, d, e) for _, t, d, e in LEVEL_CASES],
    ids=[cid for cid, *_ in LEVEL_CASES],
)
def test_level_classification(title: str, description: str, expected: Level) -> None:
    result = HeuristicClassifier().classify(_job(title, description))

    assert result.level == expected
