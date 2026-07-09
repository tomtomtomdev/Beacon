"""The ambiguity gate: when the heuristic leaves residue for the LLM to upgrade.

A classification is ambiguous exactly when no category matched — that empty set is the
residue slice 9's LLM resolves. An unspecified *level* alone is NOT ambiguous: 'unspecified'
is an honest value (SPEC §6) and not worth an LLM call when the category is already known.
"""

import pytest

from beacon.domain.classification import Category, Classification, Level

AMBIGUITY_CASES = [
    ("no-category-unspecified", frozenset(), Level.UNSPECIFIED, True),
    ("no-category-but-leveled", frozenset(), Level.SENIOR, True),
    ("has-category-unspecified", frozenset({Category.IOS}), Level.UNSPECIFIED, False),
    ("has-category-and-level", frozenset({Category.BACKEND}), Level.STAFF, False),
    ("multi-category", frozenset({Category.IOS, Category.AI_ML}), Level.SENIOR, False),
]


@pytest.mark.parametrize(
    ("categories", "level", "expected"),
    [(c, lvl, e) for _, c, lvl, e in AMBIGUITY_CASES],
    ids=[cid for cid, *_ in AMBIGUITY_CASES],
)
def test_is_ambiguous_is_empty_category_set(
    categories: frozenset[Category], level: Level, expected: bool
) -> None:
    assert Classification(categories=categories, level=level).is_ambiguous is expected
