"""Company-normalized demand ranking over a corpus of postings. Pure — no IO.

Raw posting counts answer "which employer has the biggest org", not "which role is in
demand": in a seed set where ten companies own 60% of the postings, one employer hiring a
whole team drowns out ten employers hiring one engineer each. Two pure pieces fix that.

`normalize_role` collapses a title to its role family — seniority prefixes, level
numerals, parentheticals and the post-comma/dash specialisation are noise when the
question is "what role is this". It is deliberately coarse: the ios/backend/ai-ml split
already lives in the classifier, so a family here is "software engineer", not "iOS
engineer at the payments org".

`rank_roles` then scores each family with every firm's contribution capped, so breadth
across employers outranks depth at one. Concentration rides along on each row: a family
that scores well but is 90% one employer is a fact about that employer, not the market.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

# Dropped wherever they lead or trail a title. Data, not logic: a missed variant is a new
# entry plus a parametrized row, never a branch below. "+"/"."/slash forms ("Staff+",
# "Sr.", "Staff/Lead") are handled by the token cleanup, so list only the bare words.
SENIORITY_TOKENS = frozenset(
    {
        "senior",
        "sr",
        "snr",
        "staff",
        "lead",
        "principal",
        "junior",
        "jr",
        "intern",
        "trainee",
        "associate",
        "distinguished",
        "medior",
        "mid",
        "entry",
        "level",
        "i",
        "ii",
        "iii",
        "iv",
    }
)

# A bracketed aside is never the role: "(iOS)", "(FDE)", "(m/w/d)", "(Bangkok based)".
_PARENTHETICAL = re.compile(r"[(\[][^)\]]*[)\]]")

# The role is the head of the title; everything after the first comma, pipe or spaced dash
# is the specialisation ("…, Ads Ranking", "… - Financial Services"). An unspaced hyphen is
# part of a word ("back-end") and must survive.
_SPECIALISATION = re.compile(r"\s*[,|]\s*|\s+[-–—]\s+|\s*[–—]\s*")

_EDGE_PUNCTUATION = "+.,:;"


@dataclass(frozen=True, slots=True)
class RolePosting:
    """One posting reduced to what demand analysis needs: who posted it, and as what."""

    company: str
    title: str


@dataclass(frozen=True, slots=True)
class DemandRow:
    """One role family's demand, with the concentration that produced it kept in view."""

    role: str
    postings: int
    firms: int
    score: int
    top_firm: str
    top_firm_share: float


def _is_seniority(token: str) -> bool:
    """True for 'senior', 'Sr.', 'Staff+' and compound forms like 'Staff/Lead'."""
    parts = [part.strip(_EDGE_PUNCTUATION) for part in token.split("/")]
    words = [part for part in parts if part]
    return bool(words) and all(word in SENIORITY_TOKENS for word in words)


def normalize_role(title: str) -> str:
    """Collapse a posting title to its role family — '' when nothing but seniority is left."""
    head = _SPECIALISATION.split(_PARENTHETICAL.sub(" ", title.lower()))[0]
    tokens = head.split()

    start, end = 0, len(tokens)
    while start < end and _is_seniority(tokens[start]):
        start += 1
    while end > start and _is_seniority(tokens[end - 1]):
        end -= 1

    return " ".join(tokens[start:end])


def rank_roles(
    postings: Iterable[RolePosting], *, cap: int = 3, min_firms: int = 2
) -> list[DemandRow]:
    """Rank role families by company-capped demand, widest-adoption first.

    `cap` bounds how many postings any one firm contributes to a family's score; `min_firms`
    drops families only one employer is hiring for. Ties break by firms, then postings, then
    role name, so the same corpus always produces the same table.
    """
    per_role: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for posting in postings:
        role = normalize_role(posting.title)
        if role:
            per_role[role][posting.company] += 1

    rows = [
        _row(role, by_firm, cap) for role, by_firm in per_role.items() if len(by_firm) >= min_firms
    ]
    rows.sort(key=lambda row: (-row.score, -row.firms, -row.postings, row.role))
    return rows


def _row(role: str, by_firm: Counter[str], cap: int) -> DemandRow:
    postings = sum(by_firm.values())
    # Sorted first so an even split reports the same top firm on every run.
    top_firm, top_count = max(sorted(by_firm.items()), key=lambda item: item[1])
    return DemandRow(
        role=role,
        postings=postings,
        firms=len(by_firm),
        score=sum(min(count, cap) for count in by_firm.values()),
        top_firm=top_firm,
        top_firm_share=top_count / postings,
    )
