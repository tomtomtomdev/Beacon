"""MatchRationale (§11 Tier 2) — the value object the LLM deep-match produces and the
job_match_scores.llm_rationale column stores. Pure domain: construction + JSON roundtrip."""

import json

from beacon.domain.resume import (
    MatchRationale,
    rationale_from_json,
    rationale_to_json,
)


def _rationale() -> MatchRationale:
    return MatchRationale(
        summary="Strong iOS fit with a Swift-heavy background.",
        strengths=("8 years of Swift", "Ships SwiftUI apps"),
        gaps=("No Kotlin", "Light on backend"),
        verdict="Worth applying.",
        sponsor_note="Registry-inferred sponsor in a target country.",
    )


def test_rationale_json_roundtrips() -> None:
    rationale = _rationale()

    restored = rationale_from_json(rationale_to_json(rationale))

    assert restored == rationale


def test_rationale_to_json_is_a_readable_object() -> None:
    # The column is inspectable text, not a pickle — a human (or a later migration) can read it.
    data = json.loads(rationale_to_json(_rationale()))

    assert data["summary"].startswith("Strong iOS fit")
    assert data["strengths"] == ["8 years of Swift", "Ships SwiftUI apps"]
    assert data["verdict"] == "Worth applying."
    assert data["sponsor_note"].startswith("Registry-inferred")
