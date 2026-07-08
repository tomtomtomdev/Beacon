"""Sponsorship tiers. The precedence/sort tables here are the single source of truth."""

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class SponsorTier(StrEnum):
    EXPLICIT_YES = "explicit_yes"
    REGISTRY_INFERRED = "registry_inferred"
    UNKNOWN = "unknown"
    EXPLICIT_NO = "explicit_no"


@dataclass(frozen=True, slots=True)
class SponsorSignal:
    """A sponsorship signal for one job: the resolved tier plus, when it came from
    the posting text, the sentence that decided it (None for registry/unknown)."""

    tier: SponsorTier
    evidence: str | None = None


# Explicit-text signal tables (data not logic — extend a row when a spot-check finds a
# miss, mirroring the classifier keyword tables). NO is scanned before YES so "no beats
# yes". NO uses regex because negations put words between the negator and the verb
# ("not currently able to sponsor"), which a fixed substring like "able to sponsor" would
# read as a YES; [^.!?]* keeps the gap inside one sentence.
_EXPLICIT_NO_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bno\b[^.!?]*\bsponsor",  # "no visa sponsorship", "no sponsorship"
        r"\bnot\b[^.!?]*\bsponsor",  # "not able to sponsor", "do not sponsor"
        r"\bcannot\b[^.!?]*\bsponsor",  # "cannot sponsor"
        r"\bunable\b[^.!?]*\bsponsor",  # "unable to sponsor"
        r"\bwithout\b[^.!?]*\bsponsor",  # "without visa sponsorship"
        r"\bright to work\b",  # "must have the right to work in ..."
        r"\bwork authori[sz]ation\b",  # "EU work authorization required"
        r"\bauthori[sz]ed to work\b",  # "must be authorized to work"
        r"\bgreen card holders?\b",  # "US citizens or green card holders only"
        r"\bno relocation\b",
    )
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
SORT_RANK: MappingProxyType[SponsorTier, int] = MappingProxyType(
    {
        SponsorTier.EXPLICIT_YES: 3,
        SponsorTier.REGISTRY_INFERRED: 2,
        SponsorTier.UNKNOWN: 1,
        SponsorTier.EXPLICIT_NO: 0,
    }
)


def resolve_tier(text_tier: SponsorTier | None, registry_flags: int) -> SponsorTier:
    """The one place tier precedence lives: explicit text beats registry beats unknown.

    text_tier is the posting-text signal (explicit_yes/explicit_no or None until the
    slice-6 classifier lands). registry_flags is the company's registry bitmask.
    """
    if text_tier in (SponsorTier.EXPLICIT_NO, SponsorTier.EXPLICIT_YES):
        return text_tier
    return SponsorTier.REGISTRY_INFERRED if registry_flags else SponsorTier.UNKNOWN


def tier_sort_rank(tier: SponsorTier) -> int:
    return SORT_RANK[tier]
