"""seeds/registry_rejections.csv → the reviewed rejections the matcher honours (slice 25c)."""

import pytest

from beacon.adapters.registries.rejections import parse_rejections_csv
from beacon.config import Settings
from beacon.domain.matching import RegistryRejection
from beacon.domain.registry import Registry

HEADER = "company,registry,entry,reason,reviewed_at\n"


def test_parses_one_rejection_per_row() -> None:
    text = HEADER + "Cohere,PERM,Cohere Technologies Inc.,a wireless company,2026-10-09\n"

    assert parse_rejections_csv(text) == frozenset(
        {RegistryRejection("Cohere", Registry.PERM, "Cohere Technologies Inc.")}
    )


def test_a_row_without_a_reason_is_refused() -> None:
    # The reason is the review. A rejection nobody can explain is a guess, not a judgement.
    with pytest.raises(ValueError, match="reason"):
        parse_rejections_csv(HEADER + "Cohere,PERM,Cohere Technologies Inc.,,2026-10-09\n")


def test_an_unknown_registry_is_refused() -> None:
    with pytest.raises(ValueError, match="XX"):
        parse_rejections_csv(HEADER + "Cohere,XX,Cohere Technologies Inc.,why,2026-10-09\n")


def test_the_shipped_file_parses() -> None:
    rejections = parse_rejections_csv(Settings.from_env({}).rejections_path.read_text())

    assert RegistryRejection("Cohere", Registry.PERM, "Cohere Technologies Inc.") in rejections
