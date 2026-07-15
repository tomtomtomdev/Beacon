"""Skill/category/level keyword vocabulary and the pure text-matching primitives over it.

DATA, not logic in the tables (CLAUDE.md): extend a category or fix a spot-check miss by
editing a tuple here and adding a parametrized test row — never by adding a branch to a
classifier. The word-boundary extraction functions are pure (text -> tokens / Category /
Level), so both the classifier adapter (adapters/classify/heuristic.py) and the resume
matcher (domain/resume.py, §11) read the ONE vocabulary through them.

Located in the domain because this is shared domain knowledge with two domain-facing
consumers, not an adapter's private data — see PROGRESS 2026-07-15 (moved from
adapters/classify/keywords.py so build_profile can reuse it without a domain->adapter leak).

Category keywords are matched against the job TITLE only by the classifier (heuristic.py
explains why), while build_profile matches the whole resume text. Every keyword matches on
word boundaries, so short tokens like "ml" fire on the word, never inside "html". Bare
"ai"/"go" were removed — they misfire on "AI Native" sales titles and "go-to-market"; use
phrases ("ai engineer") or the specific form ("golang"). Keep keywords to letters, digits,
spaces, hyphens and slashes — other punctuation breaks \\b.
"""

import re

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
        "aosp",
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
        "ml engineer",
        "ai engineer",
        "ai/ml",
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
        "back end",
        "django",
        "fastapi",
        "flask",
        "rails",
        "grpc",
        "golang",
        "rust",
        "java",
        "kubernetes",
        "postgres",
        "postgresql",
        "microservice",
        "microservices",
        "spring boot",
        "infrastructure",
        "infra",
        "site reliability",
        "sre",
        "devops",
        "systems engineer",
    ),
    Category.FRONTEND: (
        "frontend",
        "front-end",
        "front end",
        "react",
        "vue",
        "angular",
        "svelte",
        "css",
        "tailwind",
        "javascript",
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

# "5+ years", "5 years", "5+ yrs" — captures the number so the largest requirement wins.
_YEARS = re.compile(r"(\d+)\s*\+?\s*(?:years|yrs|year)\b", re.IGNORECASE)


def _compile(keywords: tuple[str, ...]) -> re.Pattern[str]:
    """One word-boundary alternation per keyword set: \\b(?:kw1|kw2|...)\\b, longest first
    so "jetpack compose" is preferred over "jetpack" when both could match."""
    ordered = sorted(keywords, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(kw) for kw in ordered) + r")\b")


_CATEGORY_PATTERNS: dict[Category, re.Pattern[str]] = {
    category: _compile(keywords) for category, keywords in CATEGORY_KEYWORDS.items()
}
_LEVEL_PATTERNS: dict[Level, re.Pattern[str]] = {
    level: _compile(keywords) for level, keywords in LEVEL_KEYWORDS.items()
}
# All category keywords in one alternation — the skill vocabulary a resume and a job are
# compared on (extract_skills). Longest-first so "swiftui" wins over "swift" at a position.
_ALL_SKILLS: re.Pattern[str] = _compile(
    tuple(keyword for keywords in CATEGORY_KEYWORDS.values() for keyword in keywords)
)


def extract_categories(text: str) -> frozenset[Category]:
    """The categories whose keywords appear in text (word-boundary matched, case-insensitive)."""
    lowered = text.casefold()
    return frozenset(
        category for category, pattern in _CATEGORY_PATTERNS.items() if pattern.search(lowered)
    )


def extract_skills(text: str) -> frozenset[str]:
    """The category keyword tokens present in text — the comparable skill set shared by
    build_profile (over resume text) and score_match (over a job's title+description). The
    tokens are the vocabulary's own casefolded form, so the two sides intersect cleanly."""
    return frozenset(_ALL_SKILLS.findall(text.casefold()))


def match_level(text: str) -> Level | None:
    """The highest-seniority explicit level token in text, or None when it names none."""
    lowered = text.casefold()
    matched = [level for level, pattern in _LEVEL_PATTERNS.items() if pattern.search(lowered)]
    return max(matched, key=lambda level: LEVEL_SENIORITY[level]) if matched else None


def years_of_experience(text: str) -> int | None:
    """The largest 'N years' figure in text, or None when it states none."""
    years = [int(match.group(1)) for match in _YEARS.finditer(text)]
    return max(years) if years else None


def resolve_level(*, level_text: str, years_text: str) -> Level:
    """The one level rule, shared by the classifier and the resume matcher: an explicit
    seniority token wins; otherwise a years-of-experience figure at/above the threshold
    reads senior; otherwise the level is honestly UNSPECIFIED. The two callers differ only
    in scope — the classifier reads the token from the title but years from title+body,
    while build_profile reads both from the whole resume text."""
    explicit = match_level(level_text)
    if explicit is not None:
        return explicit
    years = years_of_experience(years_text)
    return (
        Level.SENIOR if years is not None and years >= YEARS_SENIOR_THRESHOLD else Level.UNSPECIFIED
    )
