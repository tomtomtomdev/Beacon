"""HeuristicClassifier: title-driven category (multi-label) + level from title/years.

Table-driven — a spot-check miss becomes a new row here, never a branch in the classifier.
The precision cases (desc-ignored, ai-native-not-aiml, no-ml-in-html) lock in the slice-3
decision to read category from the title only, since body copy is boilerplate-contaminated.
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


# Category is read from the TITLE only (body copy is boilerplate-contaminated — see
# heuristic.py). Every expected category must therefore be derivable from the title.
CATEGORY_CASES = [
    ("ios-title", "Senior iOS Engineer", "Ship features to users", {Category.IOS}),
    ("android-title", "Android Developer", "Join the mobile team", {Category.ANDROID}),
    ("android-aosp", "AOSP Engineer", "Platform work", {Category.ANDROID}),  # real Adyen title
    ("flutter-title", "Flutter Engineer", "Cross-platform apps", {Category.FLUTTER}),
    ("aiml-ml-engineer", "ML Engineer", "Train and serve models", {Category.AI_ML}),
    ("aiml-ai-engineer", "AI Engineer", "Build agents", {Category.AI_ML}),
    ("backend-title", "Backend Engineer", "Own our services", {Category.BACKEND}),
    # Spot-check misses (real Adyen/Agoda titles): space-form "Back End", Java, SRE, infra.
    ("backend-space", "Back End Software Engineer", "", {Category.BACKEND}),
    ("backend-java", "Software Engineer (Java)", "", {Category.BACKEND}),
    ("backend-sre", "Senior Site Reliability Engineer", "", {Category.BACKEND}),
    ("backend-infra", "Staff Infrastructure Engineer", "", {Category.BACKEND}),
    # Coverage misses found in the 2026-08-18 corpus spot-check (real Databricks/Agoda/
    # OpenAI/Stripe titles): named backend specialisms the table did not carry.
    ("backend-distributed", "Software Engineer, Distributed Systems", "", {Category.BACKEND}),
    ("backend-networking", "Senior Software Engineer - Networking", "", {Category.BACKEND}),
    (
        "backend-database",
        "Senior Software Engineer - Database Engine Internals",
        "",
        {Category.BACKEND},
    ),
    ("backend-kernel", "TPU Kernel Engineer", "", {Category.BACKEND}),
    ("backend-python", "Agentic Python Engineer", "", {Category.BACKEND}),
    ("backend-platform-eng", "Senior Data Platform Engineer", "", {Category.BACKEND}),
    ("aiml-applied-ai-engineer", "Senior Applied AI Engineer", "", {Category.AI_ML}),
    ("aiml-applied-ai-scientist", "Staff Applied AI Scientist", "", {Category.AI_ML}),
    ("frontend-title", "Frontend Engineer", "Build the web UI", {Category.FRONTEND}),
    ("frontend-space", "Lead Software Engineer - Front End", "", {Category.FRONTEND}),
    ("frontend-typescript", "Principal Engineer (TypeScript)", "", {Category.FRONTEND}),
    ("frontend-nextjs", "Manager of the Technical Staff - Next.js", "", {Category.FRONTEND}),
    ("frontend-ui-engineer", "UI Engineer II", "", {Category.FRONTEND}),
    ("fullstack-title", "Full-Stack Engineer", "End to end", {Category.FULLSTACK}),
    ("multi-ios-aiml", "iOS ML Engineer", "On-device models", {Category.IOS, Category.AI_ML}),
    (
        "multi-ios-android",
        "iOS and Android Engineer",
        "Both platforms",
        {Category.IOS, Category.ANDROID},
    ),
    # "ml" must fire on the word, never inside "html".
    ("no-ml-in-html", "HTML Email Developer", "Hand-write HTML", set()),
    # Precision: description tech NEVER contaminates category — the title is a sales role.
    ("desc-ignored", "Account Executive", "We build LLMs with PyTorch and Django", set()),
    # Bare "ai" was removed so AI-company sales titles don't read as ML roles.
    ("ai-native-not-aiml", "Account Executive, AI Native", "Sell to AI startups", set()),
    # Honest empty: nothing matched (LLM fallback cleans residue in slice 9).
    ("empty", "Project Manager", "Own the roadmap and stakeholders", set()),
    # Precision guards for candidates REJECTED in the 2026-08-18 spot-check: these tokens
    # read as tech but head mostly go-to-market titles in the corpus, so the table carries
    # the narrow phrase ("platform engineer") and never the bare word ("platform").
    ("bare-platform-not-backend", "Cloud Partner Enablement Lead", "", set()),
    ("bare-aws-not-backend", "AWS Specialist Seller, Strategic Pursuits", "", set()),
    ("bare-web-not-frontend", "Manager, Web Engineering", "", set()),
    # A plain SWE title names no specialism — honest residue for the LLM tier, not a guess.
    ("plain-swe-stays-empty", "Senior Software Engineer", "", set()),
    # "Applied AI" is an org/team name at Anthropic and OpenAI, so it heads architect, GTM
    # and ops titles too — the same trap bare "ai" was removed for. Only the role-form
    # phrases ("applied ai engineer"/"scientist") are in the table.
    ("applied-ai-architect-not-aiml", "Applied AI Architect, Commercial", "", set()),
    ("applied-ai-ops-not-aiml", "Strategy & Operations, Applied AI - AMER", "", set()),
    # 2026-08-26 spot check: SWIFT the interbank network is not Swift the language. The
    # vocabulary's homograph guard drops it in a payments context with no iOS sibling
    # keyword, and keeps it when one is there.
    ("swift-the-payment-network-not-ios", "SWIFT Payments Integration Engineer", "", set()),
    ("swift-in-an-ios-payments-title", "iOS Engineer, Payments (Swift)", "", {Category.IOS}),
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
