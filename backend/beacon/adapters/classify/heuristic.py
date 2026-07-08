"""HeuristicClassifier — keyword/word-boundary category matching + title/years level.

Implements the Classifier port. Pure and offline: the sibling LLMClassifier (slice 9) will
share the port and take over only the ambiguous residue this leaves empty.
"""

import re

from beacon.adapters.classify.keywords import (
    CATEGORY_KEYWORDS,
    LEVEL_KEYWORDS,
    LEVEL_SENIORITY,
    YEARS_SENIOR_THRESHOLD,
)
from beacon.domain.classification import Category, Classification, Level
from beacon.domain.job import NormalizedJob

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


class HeuristicClassifier:
    def classify(self, job: NormalizedJob) -> Classification:
        # Category is read from the TITLE only. Descriptions are marketing-laden — an
        # AI company's every posting says "LLM", a fintech's says "backend" — so matching
        # the body cross-contaminates unrelated roles (proven in the slice-3 spot-check).
        # The title names the role; ambiguous/empty residue is the LLM fallback's job (slice 9).
        title = job.title.casefold()
        categories = frozenset(
            category for category, pattern in _CATEGORY_PATTERNS.items() if pattern.search(title)
        )
        return Classification(categories=categories, level=self._level(job))

    def _level(self, job: NormalizedJob) -> Level:
        title = job.title.casefold()
        matched = [level for level, pattern in _LEVEL_PATTERNS.items() if pattern.search(title)]
        if matched:
            return max(matched, key=lambda level: LEVEL_SENIORITY[level])
        # Years-of-experience is role-specific (not boilerplate), so it may come from the body.
        years = [int(m.group(1)) for m in _YEARS.finditer(f"{job.title}\n{job.description}")]
        if years and max(years) >= YEARS_SENIOR_THRESHOLD:
            return Level.SENIOR
        return Level.UNSPECIFIED
