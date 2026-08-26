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


# Homograph guards. A vocabulary keyword that also names something non-technical is dropped
# when the text puts it in the colliding context and no sibling keyword corroborates it.
# Appended from spot checks, never deleted (testing conventions).
HOMOGRAPH_CASES = [
    # 2026-08-26 spot check: Anthropic's "Cash Manager, Treasury" scored 80 against an iOS
    # resume off this phrase, and Adyen's "Head of Global Credit Risk" 76 the same way.
    (
        "swift-the-payment-network",
        "Own bank connectivity (SWIFT, APIs, host-to-host) for treasury operations",
        False,
    ),
    (
        "swift-messaging-in-a-credit-risk-ad",
        "Head of Global Credit Risk — SWIFT messaging across correspondent banks",
        False,
    ),
    # The guard must not cost us real iOS ads: a sibling iOS keyword corroborates the language.
    ("swift-in-an-ios-payments-ad", "Senior iOS Engineer, Payments — Swift and SwiftUI", True),
    ("swift-with-no-payments-context", "Swift and Kotlin mobile engineer", True),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [(text, expected) for _, text, expected in HOMOGRAPH_CASES],
    ids=[cid for cid, *_ in HOMOGRAPH_CASES],
)
def test_swift_the_payment_network_is_not_the_swift_language(text: str, expected: bool) -> None:
    assert ("swift" in extract_skills(text)) is expected
