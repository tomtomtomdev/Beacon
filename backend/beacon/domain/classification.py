"""Classification value objects: what category(ies) and level a posting is.

Pure data — the strategy that produces a Classification (heuristic today, LLM in slice 9)
lives behind the Classifier port in adapters/classify/. categories is multi-label; an
empty set is an honest "nothing matched", and Level.UNSPECIFIED is an honest "no signal".
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Category(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    FLUTTER = "flutter"
    AI_ML = "ai-ml"
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"


class Level(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    SENIOR = "senior"
    STAFF = "staff"
    LEAD = "lead"
    PRINCIPAL = "principal"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True, slots=True)
class Classification:
    categories: frozenset[Category]
    level: Level

    @property
    def is_ambiguous(self) -> bool:
        """True when no category matched — the residue an upgrader (the LLM classifier)
        should resolve. Level being UNSPECIFIED alone is NOT ambiguous: 'unspecified' is an
        honest value and not worth an LLM call once the category is known. The one explicit
        gate the tiered classifier reads, so 'ambiguous' is defined in exactly one place."""
        return not self.categories


def format_categories(categories: Iterable[Category]) -> str:
    """DB form: sorted, comma-joined values ("ai-ml,ios"). Stable so it diffs cleanly."""
    return ",".join(sorted(c.value for c in categories))


def parse_categories(raw: str | None) -> frozenset[Category]:
    if not raw:
        return frozenset()
    return frozenset(Category(value) for value in raw.split(","))
