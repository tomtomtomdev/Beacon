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
phrases ("ai engineer") or the specific form ("golang"). A keyword must START and END with a
letter or digit, since the alternation is wrapped in \\b: interior punctuation is fine
("next.js", "objective-c", "ai/ml"), but an edge symbol ("c++", ".net") would put \\b against
a non-word character and never match.
"""

import re
from dataclasses import dataclass

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
        # Role-form only: "Applied AI" is a team name at Anthropic/OpenAI and heads
        # architect/GTM/ops titles too — bare "applied ai" repeats the bare-"ai" mistake.
        # ("Applied AI Engineer" needs no entry; "ai engineer" already covers it.)
        "applied ai scientist",
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
        "distributed systems",
        "networking",
        "database",
        "kernel",
        "python",
        # The phrase only: bare "platform"/"cloud"/"aws" head go-to-market titles
        # ("Cloud Partner Enablement Lead", "AWS Specialist Seller") far more often
        # than engineering ones — see the rejected-candidate guards in test_classifier.
        "platform engineer",
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
        "typescript",
        "next.js",
        "nextjs",
        "ui engineer",
    ),
    Category.FULLSTACK: (
        "fullstack",
        "full-stack",
        "full stack",
    ),
}


@dataclass(frozen=True, slots=True)
class HomographGuard:
    """A keyword that also names something non-technical. The keyword is dropped from a text
    when one of `contexts` appears there and none of `corroborators` does — the corroborators
    are the sibling keywords the real technical sense practically always travels with, so a
    genuine ad keeps its skill even when it also talks about the colliding domain."""

    contexts: tuple[str, ...]
    corroborators: tuple[str, ...]


# DATA, like every other table here: a new collision is a new row plus a parametrized test
# row, never a branch in extract_skills or in a caller.
HOMOGRAPH_GUARDS: dict[str, HomographGuard] = {
    # SWIFT is the interbank messaging network as often as Swift is the language, and
    # matching is case-insensitive so the two are indistinguishable by spelling. The 2026-08-26
    # spot check had Anthropic's "Cash Manager, Treasury" (80) and Adyen's "Head of Global
    # Credit Risk" (76) reading as iOS roles off "bank connectivity (SWIFT, APIs, ...)".
    "swift": HomographGuard(
        contexts=(
            "payment",
            "payments",
            "treasury",
            "bank",
            "banks",
            "banking",
            "iso 20022",
            "sepa",
            "remittance",
            "remittances",
            "correspondent",
            "settlement",
            "settlements",
            "wire transfer",
            "wire transfers",
            "host-to-host",
        ),
        corroborators=("ios", "swiftui", "uikit", "xcode", "objective-c", "cocoa", "app store"),
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
_GUARD_PATTERNS: dict[str, tuple[re.Pattern[str], re.Pattern[str]]] = {
    keyword: (_compile(guard.contexts), _compile(guard.corroborators))
    for keyword, guard in HOMOGRAPH_GUARDS.items()
}


def _is_homograph(keyword: str, lowered: str) -> bool:
    """True when keyword matched only its non-technical homograph in this text — see
    HOMOGRAPH_GUARDS. Applied by both extractors, so the classifier and the resume matcher
    inherit the same guard from the one vocabulary."""
    patterns = _GUARD_PATTERNS.get(keyword)
    if patterns is None:
        return False
    contexts, corroborators = patterns
    return bool(contexts.search(lowered)) and not corroborators.search(lowered)


def _keywords_present(pattern: re.Pattern[str], lowered: str) -> frozenset[str]:
    """The pattern's keywords occurring in already-casefolded text, homographs dropped."""
    return frozenset(
        keyword for keyword in pattern.findall(lowered) if not _is_homograph(keyword, lowered)
    )


def extract_categories(text: str) -> frozenset[Category]:
    """The categories whose keywords appear in text (word-boundary matched, case-insensitive)."""
    lowered = text.casefold()
    return frozenset(
        category
        for category, pattern in _CATEGORY_PATTERNS.items()
        if _keywords_present(pattern, lowered)
    )


def extract_skills(text: str) -> frozenset[str]:
    """The category keyword tokens present in text — the comparable skill set shared by
    build_profile (over resume text) and score_match (over a job's title+description). The
    tokens are the vocabulary's own casefolded form, so the two sides intersect cleanly."""
    return _keywords_present(_ALL_SKILLS, text.casefold())


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
