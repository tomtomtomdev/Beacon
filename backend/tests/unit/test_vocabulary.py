"""Vocabulary extraction primitives shared by the classifier and the resume matcher (§11).

extract_categories / match_level / years_of_experience are covered via the classifier
suite; these pin the two functions the resume matcher adds: the skill-token set and the
level rule reused with a resume's single text blob.
"""

import pytest

from beacon.domain.classification import Level
from beacon.domain.vocabulary import extract_skills, resolve_level


def test_extract_skills_returns_matched_vocabulary_tokens() -> None:
    skills = extract_skills("Senior iOS Engineer with Swift, SwiftUI and some Kotlin")

    assert {"ios", "swift", "swiftui", "kotlin"} <= skills


def test_extract_skills_matches_on_word_boundary_not_substring() -> None:
    # "swift" must not fire inside "swiftui"; "ml" must not fire inside "html".
    assert extract_skills("SwiftUI only") == frozenset({"swiftui"})
    assert extract_skills("HTML and CSS templating") == frozenset({"css"})


def test_extract_skills_empty_when_no_vocabulary_present() -> None:
    assert extract_skills("Experienced project manager and communicator") == frozenset()


LEVEL_CASES = [
    ("explicit-token-wins-over-years", "Senior Engineer", "3 years", Level.SENIOR),
    ("most-senior-token-wins", "Senior Staff Engineer", "", Level.STAFF),
    ("years-promote-a-bare-title", "Engineer", "8 years building systems", Level.SENIOR),
    ("few-years-stays-unspecified", "Engineer", "2 years", Level.UNSPECIFIED),
    ("no-signal-unspecified", "Engineer", "", Level.UNSPECIFIED),
]


@pytest.mark.parametrize(
    ("level_text", "years_text", "expected"),
    [(lt, yt, e) for _, lt, yt, e in LEVEL_CASES],
    ids=[cid for cid, *_ in LEVEL_CASES],
)
def test_resolve_level(level_text: str, years_text: str, expected: Level) -> None:
    assert resolve_level(level_text=level_text, years_text=years_text) == expected
