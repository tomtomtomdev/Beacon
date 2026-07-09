"""Sponsor registries as a company-level bitmask, and the shape a registry yields.

Bitmask members are UK | NL | US | MANUAL (SPEC §5.3). There is no SE bit — the
Swedish employer-certification scheme was discontinued Dec 2023.
"""

from dataclasses import dataclass
from enum import IntFlag


class Registry(IntFlag):
    UK = 1
    NL = 2
    US = 4
    MANUAL = 8


def registry_names(flags: int) -> tuple[str, ...]:
    """The names of the registries a company matched, in bitmask definition order
    (UK, NL, US, MANUAL) — what the job-detail drawer lists for a registry_inferred tier."""
    # Iterating a flag yields its canonical members, each with a real name (mypy types
    # Enum.name as str | None, so narrow it explicitly).
    return tuple(member.name for member in Registry(flags) if member.name is not None)


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
