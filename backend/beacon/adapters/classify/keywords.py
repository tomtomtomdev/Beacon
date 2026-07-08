"""Classifier keyword tables — DATA, not logic (CLAUDE.md).

Extending a category or fixing a spot-check miss means editing a tuple here and adding a
parametrized row to tests/unit/test_classifier.py — never adding a branch to heuristic.py.

Every keyword is matched on word boundaries (see heuristic.py), so short tokens like "go"
and "ml" are safe to list: they fire on the word, never inside "going" or "html".
Keep keywords to letters, digits, spaces and hyphens — other punctuation breaks \\b anchoring.
"""

from beacon.domain.classification import Category, Level

CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.IOS: (
        "ios",
        "swift",
        "swiftui",
        "uikit",
        "objective-c",
        "xcode",
        "cocoa",
        "coredata",
        "coreml",
        "app store",
    ),
    Category.ANDROID: (
        "android",
        "kotlin",
        "jetpack",
        "jetpack compose",
        "android sdk",
    ),
    Category.FLUTTER: (
        "flutter",
        "dart",
    ),
    Category.AI_ML: (
        "ml",
        "ai",
        "machine learning",
        "deep learning",
        "pytorch",
        "tensorflow",
        "llm",
        "llms",
        "rag",
        "cuda",
        "nlp",
        "computer vision",
        "generative ai",
        "genai",
        "large language model",
    ),
    Category.BACKEND: (
        "backend",
        "back-end",
        "django",
        "fastapi",
        "flask",
        "rails",
        "grpc",
        "go",
        "golang",
        "rust",
        "kubernetes",
        "postgres",
        "postgresql",
        "microservice",
        "microservices",
        "spring boot",
    ),
    Category.FRONTEND: (
        "frontend",
        "front-end",
        "react",
        "vue",
        "angular",
        "svelte",
        "css",
        "tailwind",
    ),
    Category.FULLSTACK: (
        "fullstack",
        "full-stack",
        "full stack",
    ),
}

# Level title tokens. Ranked most-senior-wins when several appear ("Senior Staff" → staff).
LEVEL_KEYWORDS: dict[Level, tuple[str, ...]] = {
    Level.PRINCIPAL: ("principal",),
    Level.STAFF: ("staff",),
    Level.LEAD: ("lead", "tech lead", "team lead"),
    Level.SENIOR: ("senior", "sr"),
    Level.JUNIOR: ("junior", "jr", "grad", "graduate", "entry level", "entry-level"),
    Level.INTERN: ("intern", "internship"),
}

LEVEL_SENIORITY: dict[Level, int] = {
    Level.PRINCIPAL: 5,
    Level.STAFF: 4,
    Level.LEAD: 3,
    Level.SENIOR: 2,
    Level.JUNIOR: 1,
    Level.INTERN: 0,
}

# A bare title with this many years of experience (and no explicit title token) reads senior.
YEARS_SENIOR_THRESHOLD = 5
