"""Company-name normalization and fuzzy matching — the highest-risk correctness area
(CLAUDE.md). Any change here requires re-running scripts/spot_check_registry.py.

Matching rule (the Cohere rule): a seed matches a registry entry only when their
*distinctive* token sets are EQUAL, never merely overlapping. Distinctive tokens are
what remain after dropping legal suffixes, geography, and generic corporate/divisional
words. This is what lets "Cohere US, Inc." match seed "Cohere" while "Cohere Health,
Inc." does not, and why "Reddit" never matches "Redditch" (comparison is per token,
never substring).

The three token tables below are data, not logic — extend them with a fixture row and
a spot-check, never with a branch.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from beacon.domain.registry import Registry, RegistryCompany

# Legal-entity and branch designators. Compared after periods are removed, so "N.V."
# arrives as "nv" and "S.A." as "sa".
SUFFIX_TOKENS: frozenset[str] = frozenset(
    {
        "ltd",
        "limited",
        "llc",
        "llp",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "plc",
        "gmbh",
        "ag",
        "nv",
        "bv",
        "ab",
        "sa",
        "pte",
        "pbc",
        "branch",
    }
)

# Geography: countries, regions, and the branch cities that appear in "<City> Branch"
# rows. Stripped so a foreign subsidiary collapses onto the parent brand.
GEO_TOKENS: frozenset[str] = frozenset(
    {
        "uk",
        "us",
        "usa",
        "gb",
        "eu",
        "emea",
        "apac",
        "europe",
        "european",
        "netherlands",
        "ireland",
        "sweden",
        "international",
        "global",
        "worldwide",
        "london",
        "amsterdam",
    }
)

# Generic corporate/divisional words that name a *division of the same company*, safe to
# drop. Deliberately excludes words that denote a *different kind of business* sharing a
# brand name — consulting/capital/partners/investments/advisors/ventures — those stay
# distinctive and are exactly what blocks the false-positive traps.
STRUCTURAL_TOKENS: frozenset[str] = frozenset(
    {
        "operations",
        "operating",
        "software",
        "payments",
        "financial",
        "holdings",
        "group",
        "technologies",
        "technology",
        "labs",
        "solutions",
        "services",
        "markets",
        "wholesale",
        "business",
        "opco",
        "digital",
    }
)

_DROPPABLE = GEO_TOKENS | STRUCTURAL_TOKENS

# Confidence for a match reached only after geo/structural stripping (still a match, but
# less certain than an exact suffix-only-normalized hit).
FULL_CONFIDENCE = 1.0
STRIPPED_CONFIDENCE = 0.9

_TRADING_AS = re.compile(r"\s+(?:trading\s+as|t/a|dba)\s+", re.IGNORECASE)
_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class NormalizedName:
    """key is the distinctive token set (the match key); core keeps geo/structural
    tokens and is used only to tell a full-confidence hit from a stripped one."""

    key: frozenset[str]
    core: frozenset[str]


def _tokenize(name: str) -> list[str]:
    # Remove periods first so dotted abbreviations glue ("U.K"→"uk", "N.V."→"nv"); every
    # other non-alphanumeric char is a separator, so "Reddit" and "Redditch" stay whole.
    collapsed = name.casefold().replace(".", "")
    return [tok for tok in _NON_ALNUM.split(collapsed) if tok]


def normalize_name(name: str) -> NormalizedName:
    tokens = [tok for tok in _tokenize(name) if tok not in SUFFIX_TOKENS]
    core = frozenset(tokens)
    key = frozenset(tok for tok in tokens if tok not in _DROPPABLE)
    return NormalizedName(key=key, core=core)


def split_trading_as(raw: str) -> tuple[str, tuple[str, ...]]:
    """Split a registry legal name on trading-as/T/A/dba into (legal, aliases).

    The legal name may share zero tokens with the brand, so the trailing segment is kept
    as an alias for matching (e.g. "AgileBits UK Ltd trading as 1Password")."""
    legal, *rest = _TRADING_AS.split(raw)
    return legal.strip(), tuple(part.strip() for part in rest if part.strip())


def seed_name_variants(seed: str) -> tuple[str, ...]:
    """A seed's matchable names: the base name plus any parenthetical alias.

    "Bird (MessageBird)" → ("Bird", "MessageBird") — the register keeps the renamed
    legal name, so both must be tried."""
    aliases = [inner.strip() for inner in _PARENTHETICAL.findall(seed) if inner.strip()]
    base = _PARENTHETICAL.sub("", seed).strip()
    return (base, *aliases)


def match_confidence(seed_name: str, entry: RegistryCompany) -> float | None:
    """Best confidence that this seed is this registry entry, or None below threshold.

    Distinctive token sets must be equal (the Cohere rule). Full confidence when the
    suffix-only-normalized forms already agree; reduced when geo/structural tokens had
    to be dropped to reach equality."""
    seeds = [normalize_name(variant) for variant in seed_name_variants(seed_name)]
    candidates = [normalize_name(name) for name in (entry.name, *entry.aliases)]

    best: float | None = None
    for seed in seeds:
        if not seed.key:
            continue
        for candidate in candidates:
            if seed.key != candidate.key:
                continue
            confidence = FULL_CONFIDENCE if seed.core == candidate.core else STRIPPED_CONFIDENCE
            best = confidence if best is None else max(best, confidence)
    return best


@dataclass(frozen=True, slots=True)
class RegistryMatch:
    """The combined verdict for one company across every registry it was checked against."""

    flags: Registry
    confidence: float | None
    evidence: str | None


def match_company(
    seed_name: str, entries_by_registry: Mapping[Registry, Sequence[RegistryCompany]]
) -> RegistryMatch:
    """Match one seed name against every registry's entries, OR-ing the bits that hit.

    Registry match is company-level: a registry contributes its bit on the single best
    entry hit (multi-entity companies are counted once). Confidence is the best across
    registries; evidence keeps a per-registry audit line."""
    flags = Registry(0)
    confidences: list[float] = []
    reasons: list[str] = []
    for registry, entries in entries_by_registry.items():
        best_entry = _best_entry(seed_name, entries)
        if best_entry is None:
            continue
        confidence, entry = best_entry
        flags |= registry
        confidences.append(confidence)
        reasons.append(f"{registry.name} {entry.evidence or f'{confidence:.2f}'}")
    return RegistryMatch(
        flags=flags,
        confidence=max(confidences) if confidences else None,
        evidence="; ".join(reasons) if reasons else None,
    )


def _best_entry(
    seed_name: str, entries: Sequence[RegistryCompany]
) -> tuple[float, RegistryCompany] | None:
    best: tuple[float, RegistryCompany] | None = None
    for entry in entries:
        confidence = match_confidence(seed_name, entry)
        if confidence is not None and (best is None or confidence > best[0]):
            best = (confidence, entry)
    return best
