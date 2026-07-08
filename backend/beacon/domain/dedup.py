"""Cross-source duplicate detection (SPEC §5 "Dedup strategy", key 2).

Pure logic: the same role posted on two boards should collapse to one canonical
row. Two postings are duplicates when they share the same company, the same
normalized title and country, AND their descriptions simhash within a small
Hamming distance. The exact title+country match is the primary guard against
false merges ("Senior iOS" vs "Senior Android" never collide); the simhash only
has to reject the rare generic-title collision ("Software Engineer" twice at one
company for two unrelated roles), which shows up as a large Hamming distance.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

SIMHASH_BITS = 64
# Lenient by design: title+country+company equality already gates a group, so this
# only separates "same posting, reformatted on another board" from "different role,
# same generic title". Job descriptions are short (~40 tokens), so a reformatted
# footer flips ~5-6 bits while a genuinely different role sits ~19+ bits away — 8
# lands in that gap with margin, favouring merge (one row) over the worse sin of
# showing the same job twice.
HAMMING_THRESHOLD = 8

_TOKEN = re.compile(r"[a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")
_MASK = (1 << SIMHASH_BITS) - 1


@dataclass(frozen=True, slots=True)
class DedupRow:
    """The minimum a persisted job exposes to the canonicalizer."""

    id: int
    company_id: int
    title: str
    country: str | None
    description: str


def normalize_title(title: str) -> str:
    """Case- and whitespace-insensitive title key. Deliberately conservative:
    punctuation differences keep titles distinct, so we under-merge rather than
    fuse two roles that merely share a stem."""
    return _WHITESPACE.sub(" ", title.strip().lower())


def _token_hash(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest())


def simhash(text: str) -> int:
    """64-bit Charikar simhash over lowercased alphanumeric tokens, weighted by
    frequency. Deterministic across processes (blake2b, not the salted builtin)."""
    counts: dict[str, int] = {}
    for token in _TOKEN.findall(text.lower()):
        counts[token] = counts.get(token, 0) + 1

    weights = [0] * SIMHASH_BITS
    for token, weight in counts.items():
        token_hash = _token_hash(token)
        for bit in range(SIMHASH_BITS):
            weights[bit] += weight if token_hash >> bit & 1 else -weight

    fingerprint = 0
    for bit in range(SIMHASH_BITS):
        if weights[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming(a: int, b: int) -> int:
    return ((a ^ b) & _MASK).bit_count()


def _grouping_key(row: DedupRow) -> tuple[int, str, str | None]:
    return (row.company_id, normalize_title(row.title), row.country)


def _cluster_group(group: Sequence[DedupRow]) -> dict[int, int]:
    """Union-find within one candidate group: near-simhash rows collapse to the
    lowest id in their cluster. Returns each id → its canonical id."""
    fingerprints = {row.id: simhash(row.description) for row in group}
    parent = {row.id: row.id for row in group}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ordered = sorted(fingerprints)
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if hamming(fingerprints[left], fingerprints[right]) <= HAMMING_THRESHOLD:
                parent[find(right)] = find(left)  # lower id sorts first, so it wins as root

    return {job_id: find(job_id) for job_id in ordered}


def assign_canonicals(rows: Sequence[DedupRow]) -> dict[int, int]:
    """Map every row id to its canonical row id (itself when it is canonical).

    Rows sharing (company, normalized title, country) form a candidate group; within
    a group, near-simhash postings cluster transitively and the lowest id — the
    earliest-inserted row — is the canonical. Idempotent: re-running on already-linked
    rows yields the same mapping."""
    groups: dict[tuple[int, str, str | None], list[DedupRow]] = {}
    for row in rows:
        groups.setdefault(_grouping_key(row), []).append(row)

    canonical: dict[int, int] = {}
    for group in groups.values():
        canonical.update(_cluster_group(group))
    return canonical
