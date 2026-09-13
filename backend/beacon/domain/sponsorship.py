"""Sponsorship tiers. The precedence/sort tables here are the single source of truth."""

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class SponsorTier(StrEnum):
    EXPLICIT_YES = "explicit_yes"
    NOT_REQUIRED = "not_required"
    REGISTRY_INFERRED = "registry_inferred"
    UNKNOWN = "unknown"
    EXPLICIT_NO = "explicit_no"


@dataclass(frozen=True, slots=True)
class SponsorSignal:
    """A sponsorship signal for one job: the resolved tier plus, when it came from
    the posting text, the sentence that decided it (None for registry/unknown)."""

    tier: SponsorTier
    evidence: str | None = None


# The home market (SPEC §3/§4): the one country whose jobs need no visa, because the reader
# already holds the right to work there. A location predicate, so it is the job's country that
# decides — see resolve_tier.
HOME_COUNTRY = "ID"


# Explicit-text signal tables (data not logic — extend a row when a spot-check finds a
# miss, mirroring the classifier keyword tables). NO is scanned before YES so "no beats
# yes".
#
# The NO table is GENERATED from negator x object, because a refusal names the same thing
# the YES table does and merely negates it: any object the YES side matches ("visa
# support") needs a negated twin, or the refusal falls through to YES and inverts the tier
# — the 2026-08-18 "NOTE: NO VISA SUPPORT" bug, where every negation demanded the literal
# word "sponsor". Adding an object here is therefore the fix for a whole class, not one
# phrasing.
_NEGATORS: tuple[str, ...] = ("no", "not", "cannot", "unable", "without", "nor")

# The sponsorship-ish objects a negator can flip. Substring-open on the right so
# "sponsor" also covers "sponsors"/"sponsorship".
_NEGATED_OBJECTS: tuple[str, ...] = (
    "sponsor",
    "visa support",
    "visa assistance",
    "work permit",
    "relocation",
)

# Max characters between a negator and its object. Descriptions arrive with newlines
# collapsed, so a bullet list is ONE run-on "sentence" and an unbounded gap pairs a
# stray "not" with an unrelated object 200 words later ("you will not only manage a
# portfolio of high-value PE/VC sponsors" read as a visa refusal). 40 comfortably spans
# real interjections ("not currently able to sponsor", "not eligible for visa or
# relocation support") while keeping the pair in the same clause.
_NEGATION_GAP = 40

# Requirements that are refusals on their own — no negator needed.
_WORK_AUTHORIZATION_PATTERNS: tuple[str, ...] = (
    r"\bright to work\b",  # "must have the right to work in ..."
    r"\bwork authori[sz]ation\b",  # "EU work authorization required"
    r"\bauthori[sz]ed to work\b",  # "must be authorized to work"
    r"\bgreen card holders?\b",  # "US citizens or green card holders only"
)

# A residency precondition is a refusal on its own and names no sponsorship word, which is why
# nothing above caught it. The discriminating word is "already": it separates "you must ALREADY
# live here" (a refusal — a relocating candidate is out) from a plain statement of where the
# desk is, which sponsoring employers make constantly.
#
# The bare modal forms ("must be based in X", "must reside in X") were tried on 2026-09-02 and
# REJECTED by the spot check over 8,918 live postings: they flipped 23 jobs wrongly, including
# Discord's "Candidates must reside in OR BE WILLING TO RELOCATE TO the San Francisco Bay Area"
# (x21 — an explicit relocation offer) and Anthropic's "Must be located in San Francisco" on a
# posting that also says "We do sponsor visas!". Since NO beats YES by precedence, matching the
# bare form would have inverted a sponsoring employer's work-location line into a refusal.
# Requiring "already" keeps the Bjak class (which says both) and drops every false positive.
_RESIDENCY_VERBS: tuple[str, ...] = ("be based", "be located", "reside", "residing", "be living")
# Spans "already be based", "already, be located", "already need to reside".
_RESIDENCY_GAP = 15

_EXPLICIT_NO_PATTERNS: tuple[re.Pattern[str], ...] = (
    tuple(
        re.compile(rf"\b{negator}\b[^.!?]{{0,{_NEGATION_GAP}}}\b{obj}", re.IGNORECASE)
        for negator in _NEGATORS
        for obj in _NEGATED_OBJECTS
    )
    + tuple(
        re.compile(rf"\balready\b[^.!?]{{0,{_RESIDENCY_GAP}}}\b{verb}\b", re.IGNORECASE)
        for verb in _RESIDENCY_VERBS
    )
    + tuple(re.compile(pattern, re.IGNORECASE) for pattern in _WORK_AUTHORIZATION_PATTERNS)
)
# YES is also regex: postings phrase offers loosely ("relocation and family support are
# offered", "with relocation and work visa provided"), so [^.!?]* bridges the gap between
# the perk and the offering verb. relocation is treated as a positive signal here per the
# PLAN's yes list ("relocation package"); the verb requirement ("provide"/"provided"/…)
# is what separates an offer from a mere requirement ("it will require a relocation …").
_EXPLICIT_YES_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bvisa sponsorship\b[^.!?]*\b(available|provided|offered)\b",
        r"\b(offer|offers|provide|provides|full)\b[^.!?]*\bvisa sponsorship\b",
        r"\bwe (do |will |can )?sponsor\b",  # "we sponsor", "we do sponsor", "we can sponsor"
        r"\bsponsor (work )?visas?\b",  # "sponsor work visas", "sponsor visas"
        r"\b(happy|able|willing|glad) to sponsor\b",
        r"\bwork permit assistance\b",
        r"\bvisa (support|assistance)\b",
        # relocation offered/provided — perk + offering verb, in either order
        r"\brelocation\b[^.!?]*\b(package|assistance|support|provided|offered|covered)\b",
        r"\b(provide|provides|offer|offers|cover|covers)\b[^.!?]*\brelocation\b",
    )
)

# Sentence boundary: terminator + whitespace, or one/more newlines.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# normalize_description collapses newlines, so HTML bullet lists become one run-on
# "sentence". Evidence is clipped to this many chars of context each side of the match
# so the drawer highlights a readable phrase, not a paragraph.
_EVIDENCE_RADIUS = 80


def _evidence(sentence: str, match: re.Match[str]) -> str:
    """The matched sentence, or a word-trimmed window around the match with ellipses
    when the sentence is a long run-on."""
    if len(sentence) <= 2 * _EVIDENCE_RADIUS:
        return sentence
    start = max(0, match.start() - _EVIDENCE_RADIUS)
    end = min(len(sentence), match.end() + _EVIDENCE_RADIUS)
    snippet = sentence[start:end].strip()
    if start > 0:  # drop the leading partial word
        snippet = "… " + snippet.partition(" ")[2]
    if end < len(sentence):  # drop the trailing partial word
        snippet = snippet.rpartition(" ")[0] + " …"
    return snippet


def _first_match(sentence: str, patterns: tuple[re.Pattern[str], ...]) -> re.Match[str] | None:
    for pattern in patterns:
        match = pattern.search(sentence)
        if match is not None:
            return match
    return None


def detect_sponsorship(text: str) -> SponsorSignal | None:
    """Read explicit_yes/explicit_no out of posting text, or None when it is silent.

    explicit_no takes precedence over explicit_yes (a hard work-authorization
    requirement disqualifies regardless of any perk mentioned elsewhere), so every
    sentence is scanned for a NO signal before any YES signal is considered. The
    returned evidence is the deciding sentence, clipped around the matched phrase."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    for tier, patterns in (
        (SponsorTier.EXPLICIT_NO, _EXPLICIT_NO_PATTERNS),
        (SponsorTier.EXPLICIT_YES, _EXPLICIT_YES_PATTERNS),
    ):
        for sentence in sentences:
            match = _first_match(sentence, patterns)
            if match is not None:
                return SponsorSignal(tier=tier, evidence=_evidence(sentence, match))
    return None


# Drives /jobs default ordering (sort_rank DESC, posted_at DESC). A soft signal:
# explicit_no sorts last but is never hidden, and no tier ever filters by default.
#
# not_required sits third by SPEC §4: a confirmed sponsor abroad still outranks staying —
# the tool exists to find a way out — but a certain home-market role outranks every
# speculative tier. Not a stored column: adapters/persistence/jobs.py builds its ORDER BY
# CASE from this table, so renumbering here is the whole change.
SORT_RANK: MappingProxyType[SponsorTier, int] = MappingProxyType(
    {
        SponsorTier.EXPLICIT_YES: 4,
        SponsorTier.NOT_REQUIRED: 3,
        SponsorTier.REGISTRY_INFERRED: 2,
        SponsorTier.UNKNOWN: 1,
        SponsorTier.EXPLICIT_NO: 0,
    }
)


def resolve_tier(
    text_tier: SponsorTier | None, registry_flags: int, country: str | None
) -> SponsorTier:
    """The one place tier precedence lives: home market first, then explicit text beats
    registry beats unknown.

    `country` is the JOB's country, never the company's HQ — a Jakarta req posted by a
    Singapore-HQ employer (Grab, Agoda) is still a home-market job. The home predicate is
    evaluated BEFORE the text chain and sits outside it: "no sponsorship needed" is not a
    stronger or weaker claim about sponsorship, it is the absence of the question, so
    folding it into the chain would corrupt a precedence CLAUDE.md pins as single-source.
    It also settles the one genuinely ambiguous case — a Jakarta ad reading "must have the
    right to work in Indonesia" is not_required, not explicit_no, because the reader
    already holds that right.

    text_tier is the posting-text signal (explicit_yes/explicit_no or None when the text is
    silent). registry_flags is the company's registry bitmask. A caller with no job country
    in hand (the company-level registry paths) passes None and gets the text/registry chain.
    """
    if country == HOME_COUNTRY:
        return SponsorTier.NOT_REQUIRED
    if text_tier in (SponsorTier.EXPLICIT_NO, SponsorTier.EXPLICIT_YES):
        return text_tier
    return SponsorTier.REGISTRY_INFERRED if registry_flags else SponsorTier.UNKNOWN


def tier_sort_rank(tier: SponsorTier) -> int:
    return SORT_RANK[tier]
