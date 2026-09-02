import pytest

from beacon.domain.registry import Registry
from beacon.domain.sponsorship import (
    SponsorSignal,
    SponsorTier,
    detect_sponsorship,
    resolve_tier,
    tier_sort_rank,
)


@pytest.mark.parametrize(
    ("text_tier", "registry_flags", "expected"),
    [
        # Slice 2: no text classifier yet, so text_tier is None; registry drives the tier.
        (None, 0, SponsorTier.UNKNOWN),
        (None, int(Registry.UK), SponsorTier.REGISTRY_INFERRED),
        (None, int(Registry.NL | Registry.US), SponsorTier.REGISTRY_INFERRED),
        (None, int(Registry.MANUAL), SponsorTier.REGISTRY_INFERRED),
        # Precedence (CLAUDE.md): explicit text beats registry, no beats yes.
        (SponsorTier.EXPLICIT_YES, 0, SponsorTier.EXPLICIT_YES),
        (SponsorTier.EXPLICIT_YES, int(Registry.UK), SponsorTier.EXPLICIT_YES),
        (SponsorTier.EXPLICIT_NO, int(Registry.UK), SponsorTier.EXPLICIT_NO),
    ],
    ids=[
        "no-flags-unknown",
        "uk-flag-registry_inferred",
        "multi-flag-registry_inferred",
        "manual-flag-registry_inferred",
        "explicit_yes-no-flags",
        "explicit_yes-beats-registry",
        "explicit_no-beats-registry",
    ],
)
def test_resolve_tier(
    text_tier: SponsorTier | None, registry_flags: int, expected: SponsorTier
) -> None:
    assert resolve_tier(text_tier, registry_flags) == expected


def test_tier_sort_rank_matches_domain_table() -> None:
    assert tier_sort_rank(SponsorTier.EXPLICIT_YES) == 3
    assert tier_sort_rank(SponsorTier.REGISTRY_INFERRED) == 2
    assert tier_sort_rank(SponsorTier.UNKNOWN) == 1
    assert tier_sort_rank(SponsorTier.EXPLICIT_NO) == 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # yes phrases (PLAN slice 6 list + common variants)
        ("Visa sponsorship available for the right candidate.", SponsorTier.EXPLICIT_YES),
        ("We sponsor work visas for exceptional engineers.", SponsorTier.EXPLICIT_YES),
        ("A generous relocation package is offered.", SponsorTier.EXPLICIT_YES),
        ("We provide work permit assistance.", SponsorTier.EXPLICIT_YES),
        ("We are happy to sponsor visas.", SponsorTier.EXPLICIT_YES),
        # Real spot-check hits (Agoda, slice-6 acceptance): loose relocation-offer phrasing.
        (
            "This role is based in Bangkok, Thailand (Relocation Provided).",
            SponsorTier.EXPLICIT_YES,
        ),
        ("World-class relocation and family support are offered.", SponsorTier.EXPLICIT_YES),
        ("We provide complete relocation for you and your family.", SponsorTier.EXPLICIT_YES),
        # no phrases
        ("You must have the right to work in the EU.", SponsorTier.EXPLICIT_NO),
        ("No visa sponsorship is provided for this role.", SponsorTier.EXPLICIT_NO),
        ("US citizens or green card holders only.", SponsorTier.EXPLICIT_NO),
        ("EU work authorization required.", SponsorTier.EXPLICIT_NO),
        ("We are unable to sponsor visas at this time.", SponsorTier.EXPLICIT_NO),
        # Real spot-check miss (Anthropic Fellows, slice-6 acceptance): "not currently
        # able to sponsor" — words between the negation and the verb must not read as YES.
        ("We are not currently able to sponsor visas for fellows.", SponsorTier.EXPLICIT_NO),
        ("We do not offer visa sponsorship for this position.", SponsorTier.EXPLICIT_NO),
        # Real spot-check misses (2026-08-18, live corpus): a refusal phrased with
        # "support"/"assistance" instead of "sponsor" inverted to EXPLICIT_YES, because
        # every negation pattern required the word "sponsor" while the YES table matched
        # the bare phrase "visa support". These are verbatim Airbnb/HN posting text.
        ("NOTE: NO VISA SUPPORT", SponsorTier.EXPLICIT_NO),
        ("No Relocation and Visa Support", SponsorTier.EXPLICIT_NO),
        ("no visa support now or in the future", SponsorTier.EXPLICIT_NO),
        ("This role is not eligible for relocation support.", SponsorTier.EXPLICIT_NO),
        (
            "This role is based in Milan, and is not eligible for visa or relocation support.",
            SponsorTier.EXPLICIT_NO,
        ),
        # Real spot-check misses (2026-09-02, live corpus): a residency *precondition* is a
        # refusal on its own — it rules out the relocating candidate Beacon exists for, and
        # names no sponsorship word at all, so nothing in the NO table saw it. Verbatim Bjak
        # "AI Neobank App" text, which sat at fit 72 across seven target countries as
        # `unknown` (i.e. sorted as neutral) while being unreachable.
        (
            "We are hiring specifically for this market, "
            "so applicants should already be based in Germany.",
            SponsorTier.EXPLICIT_NO,
        ),
        ("Applicants must already be based in Ireland.", SponsorTier.EXPLICIT_NO),
        ("You must already reside in the Netherlands.", SponsorTier.EXPLICIT_NO),
        ("Candidates should already be living in Sweden.", SponsorTier.EXPLICIT_NO),
    ],
    ids=[
        "yes-visa-sponsorship-available",
        "yes-we-sponsor-work-visas",
        "yes-relocation-package",
        "yes-work-permit-assistance",
        "yes-happy-to-sponsor",
        "no-right-to-work-eu",
        "no-no-visa-sponsorship",
        "no-green-card-holders-only",
        "no-work-authorization-required",
        "no-unable-to-sponsor",
        "no-not-currently-able-to-sponsor",
        "no-do-not-offer-sponsorship",
        "yes-relocation-provided",
        "yes-relocation-and-family-support-offered",
        "yes-provide-complete-relocation",
        "no-bare-no-visa-support",
        "no-relocation-and-visa-support",
        "no-visa-support-now-or-future",
        "no-not-eligible-for-relocation-support",
        "no-not-eligible-for-visa-or-relocation",
        "no-should-already-be-based-in-country",
        "no-must-already-be-based-in-country",
        "no-must-already-reside-in-country",
        "no-should-already-be-living-in-country",
    ],
)
def test_detect_sponsorship_tier(text: str, expected: SponsorTier) -> None:
    signal = detect_sponsorship(text)

    assert signal is not None
    assert signal.tier == expected


def test_detect_sponsorship_returns_the_matched_sentence_as_evidence() -> None:
    text = (
        "We are a fast-growing team building payments infrastructure.\n"
        "Visa sponsorship is available for this role.\n"
        "Apply today."
    )

    signal = detect_sponsorship(text)

    assert signal == SponsorSignal(
        tier=SponsorTier.EXPLICIT_YES, evidence="Visa sponsorship is available for this role."
    )


def test_detect_sponsorship_clips_evidence_from_a_run_on_sentence() -> None:
    # normalize_description collapses HTML bullet lists into one long run-on with no
    # sentence breaks; evidence must be a readable window around the phrase, not the blob.
    run_on = (
        "Responsibilities include "
        + "owning cross-functional initiatives " * 12
        + "and to participate you must have work authorization in the US, "
        + "and other duties " * 12
        + "as assigned."
    )

    signal = detect_sponsorship(run_on)

    assert signal is not None
    assert signal.tier == SponsorTier.EXPLICIT_NO
    assert signal.evidence is not None
    assert "work authorization in the US" in signal.evidence
    assert signal.evidence.startswith("… ") and signal.evidence.endswith(" …")
    assert len(signal.evidence) < len(run_on)


def test_detect_sponsorship_no_beats_yes_when_both_appear() -> None:
    # A posting mentioning both a perk and a hard requirement: explicit_no wins (CLAUDE.md),
    # and the evidence points at the disqualifying sentence.
    text = "We offer a relocation package. However, you must have the right to work in the UK."

    signal = detect_sponsorship(text)

    assert signal is not None
    assert signal.tier == SponsorTier.EXPLICIT_NO
    assert signal.evidence is not None
    assert "right to work" in signal.evidence.casefold()


@pytest.mark.parametrize(
    "text",
    [
        "Build delightful products with a talented team.",
        # A relocation *requirement*, not an offer — must stay silent (Agoda spot-check).
        "It will require a relocation in case you live outside of Shanghai.",
        # "sponsorship" in a non-visa sense — organizational, not a work-permit signal.
        "Provide mentorship and horizontal sponsorship across the organization.",
        "Serve as the executive sponsor for our largest UK merchants.",
        # Real corpus false-NO (2026-08-18): an unbounded gap between the negation and the
        # object let a distant, unrelated "not" pair with investor "sponsors". The negation
        # must stay near its object, so a far-apart pair reads as no signal at all.
        (
            "In this senior role, you will not only manage a portfolio of high-value "
            "PE/VC sponsors but will also own the commercial relationship."
        ),
    ],
    ids=[
        "no-signal",
        "relocation-requirement",
        "org-sponsorship",
        "executive-sponsor",
        "distant-not-with-investor-sponsors",
    ],
)
def test_detect_sponsorship_returns_none_when_no_signal(text: str) -> None:
    assert detect_sponsorship(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "This role is based in Stockholm.",
        "Our engineering team is based in Amsterdam and London.",
        "You will be based in our Dublin office alongside the platform team.",
        # Verbatim, 2026-09-02 spot check over 8,918 live postings — the exact phrasings the
        # bare modal form got wrong. Discord x21 offers relocation in the same breath, and
        # Anthropic's line sits in a posting that also reads "We do sponsor visas!".
        "Candidates must reside in or be willing to relocate to the San Francisco Bay Area.",
        "Must be located in San Francisco",
        "This role is remote, but candidates must be based in Germany.",
    ],
    ids=[
        "states-location",
        "team-location",
        "office-location",
        "residency-or-willing-to-relocate",
        "work-location-of-a-sponsoring-employer",
        "bare-must-be-based-is-ambiguous",
    ],
)
def test_a_location_requirement_without_already_is_not_a_refusal(text: str) -> None:
    """Only "already" makes a location line a refusal. A bare "must be based in X" is how a
    sponsoring employer states where the desk is, so matching it would invert a whole class of
    reachable jobs — NO beats YES, so the damage would be silent."""
    assert detect_sponsorship(text) is None
