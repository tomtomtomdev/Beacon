"""Sponsor registries as a company-level bitmask, and the shape a registry yields.

Bitmask members are UK | NL | US | MANUAL | IE | CA (SPEC §5.3). There is no SE bit — the
Swedish employer-certification scheme was discontinued Dec 2023.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntFlag

# Registries are refreshed by hand on a monthly-ish cadence, so they never quarantine — they
# just nag when a snapshot goes stale (SPEC §7: fetched_at older than 45 days → digest warning).
REGISTRY_STALE_AFTER_DAYS = 45


class Registry(IntFlag):
    """Values are FROZEN and members are only ever appended: registry_flags is a stored
    integer column, so renumbering a bit would silently re-label every company already
    matched in the DB. IE + CA were appended in slice 14 (hence MANUAL keeping bit 8)."""

    UK = 1
    NL = 2
    US = 4
    MANUAL = 8
    IE = 16
    CA = 32


# The registers that are published as a downloadable snapshot, and can therefore be missing
# from this box. Derived from the enum rather than listed, so a bit appended later is covered by
# the coverage view for free. MANUAL is excluded deliberately: it is the hand-flag bit
# (`refresh.py --flag`), not a register, so it has no snapshot that could be absent.
SNAPSHOT_REGISTRIES: tuple[Registry, ...] = tuple(r for r in Registry if r is not Registry.MANUAL)


def count_per_registry(mask_counts: Mapping[int, int]) -> dict[Registry, int]:
    """Split a registry_flags histogram (mask → how many companies carry exactly that mask)
    into a count per bit. A company matched by two registers counts once for each, so these
    totals deliberately do not sum to the number of companies. Masks of 0 contribute nothing."""
    counts: dict[Registry, int] = {}
    for mask, companies in mask_counts.items():
        for member in Registry(mask):
            counts[member] = counts.get(member, 0) + companies
    return counts


def registry_names(flags: int) -> tuple[str, ...]:
    """The names of the registries a company matched, in bitmask definition order
    (UK, NL, US, MANUAL, IE, CA) — what the drawer lists for a registry_inferred tier."""
    # Iterating a flag yields its canonical members, each with a real name (mypy types
    # Enum.name as str | None, so narrow it explicitly).
    return tuple(member.name for member in Registry(flags) if member.name is not None)


@dataclass(frozen=True, slots=True)
class RegistryMeta:
    """A registry snapshot's freshness bookkeeping (the registries_meta table). `registry` is
    the bitmask member name (UK/NL/US/MANUAL/IE/CA); `fetched_at` is when it was ingested."""

    registry: str
    fetched_at: datetime
    row_count: int

    def is_stale(self, *, now: datetime, max_age_days: int = REGISTRY_STALE_AFTER_DAYS) -> bool:
        return (now - self.fetched_at) > timedelta(days=max_age_days)


def stale_registries(
    metas: Iterable[RegistryMeta],
    *,
    now: datetime,
    max_age_days: int = REGISTRY_STALE_AFTER_DAYS,
) -> tuple[RegistryMeta, ...]:
    """The snapshots older than the staleness window — the digest's registry-nag lines."""
    return tuple(m for m in metas if m.is_stale(now=now, max_age_days=max_age_days))


@dataclass(frozen=True, slots=True)
class RegistryCompany:
    """One organisation as a registry lists it, ready for name matching.

    aliases hold trading-as / dba names (the legal name may share zero tokens
    with the brand). evidence is free text kept for the match audit trail
    (KvK number, certified-filing count, sponsor route, …).
    """

    name: str
    aliases: tuple[str, ...] = ()
    evidence: str = ""
