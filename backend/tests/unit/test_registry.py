from datetime import UTC, datetime, timedelta

import pytest

from beacon.domain.registry import (
    REGISTRY_STALE_AFTER_DAYS,
    SNAPSHOT_REGISTRIES,
    Registry,
    RegistryCompany,
    RegistryMeta,
    count_per_registry,
    registry_names,
    stale_registries,
)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def _meta(registry: str, days_ago: int) -> RegistryMeta:
    return RegistryMeta(registry=registry, fetched_at=NOW - timedelta(days=days_ago), row_count=100)


def test_registry_fresh_within_the_window_is_not_stale() -> None:
    fresh = _meta("UK", days_ago=REGISTRY_STALE_AFTER_DAYS - 1)

    assert fresh.is_stale(now=NOW) is False


def test_registry_past_the_window_is_stale() -> None:
    old = _meta("UK", days_ago=REGISTRY_STALE_AFTER_DAYS + 1)

    assert old.is_stale(now=NOW) is True


def test_stale_registries_returns_only_the_stale_ones() -> None:
    metas = [
        _meta("UK", days_ago=10),
        _meta("NL", days_ago=60),
        _meta("US", days_ago=50),
    ]

    stale = stale_registries(metas, now=NOW)

    assert [m.registry for m in stale] == ["NL", "US"]


def test_registry_flags_bitmask() -> None:
    # SPEC §5.3: IE + CA joined the mask in slice 14. No SE bit exists — the Swedish
    # employer-certification scheme was discontinued Dec 2023. Members are additive and
    # their values are FROZEN: registry_flags is a stored integer, so renumbering an
    # existing bit would silently re-label every matched company already in the DB.
    assert {r.name for r in Registry} == {"UK", "NL", "US", "MANUAL", "IE", "CA"}
    assert (int(Registry.UK), int(Registry.NL), int(Registry.US), int(Registry.MANUAL)) == (
        1,
        2,
        4,
        8,
    )
    assert (int(Registry.IE), int(Registry.CA)) == (16, 32)


def test_flags_compose_and_test_by_bit() -> None:
    flags = Registry.UK | Registry.NL

    assert flags & Registry.UK
    assert flags & Registry.NL
    assert not flags & Registry.US
    assert int(flags) == int(Registry.UK) + int(Registry.NL)


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (0, ()),
        (int(Registry.UK), ("UK",)),
        (int(Registry.MANUAL), ("MANUAL",)),
        (int(Registry.UK | Registry.NL), ("UK", "NL")),
        (
            int(Registry.UK | Registry.NL | Registry.US | Registry.MANUAL),
            ("UK", "NL", "US", "MANUAL"),
        ),
        (
            int(
                Registry.UK
                | Registry.NL
                | Registry.US
                | Registry.MANUAL
                | Registry.IE
                | Registry.CA
            ),
            ("UK", "NL", "US", "MANUAL", "IE", "CA"),
        ),
    ],
    ids=["none", "uk", "manual", "uk-nl", "uk-nl-us-manual", "all"],
)
def test_registry_names_decodes_the_bitmask_in_definition_order(
    flags: int, expected: tuple[str, ...]
) -> None:
    assert registry_names(flags) == expected


def test_registry_company_carries_aliases_and_evidence() -> None:
    entry = RegistryCompany(
        name="AgileBits UK Ltd",
        aliases=("1Password",),
        evidence="Skilled Worker",
    )

    assert entry.name == "AgileBits UK Ltd"
    assert entry.aliases == ("1Password",)
    assert entry.evidence == "Skilled Worker"


def test_registry_company_defaults_to_no_aliases_or_evidence() -> None:
    entry = RegistryCompany(name="Spotify Limited")

    assert entry.aliases == ()
    assert entry.evidence == ""


def test_snapshot_registries_is_every_bit_except_the_hand_flag() -> None:
    # Derived from the enum, never listed by hand: a bit appended later is a register that
    # can go missing, and the coverage view must report it without anyone remembering to.
    # MANUAL is the --flag bit — there is no snapshot to be missing.
    assert set(SNAPSHOT_REGISTRIES) == set(Registry) - {Registry.MANUAL}
    assert [r.name for r in SNAPSHOT_REGISTRIES] == ["UK", "NL", "US", "IE", "CA"]


@pytest.mark.parametrize(
    ("mask_counts", "expected"),
    [
        ({}, {}),
        ({0: 2140}, {}),
        ({int(Registry.IE): 20}, {Registry.IE: 20}),
        # The case that rules out passing a GROUP BY registry_flags straight through: one
        # company carrying both bits counts once for each.
        (
            {int(Registry.IE): 20, int(Registry.CA): 9, int(Registry.IE | Registry.CA): 1},
            {Registry.IE: 21, Registry.CA: 10},
        ),
        ({int(Registry.MANUAL): 3}, {Registry.MANUAL: 3}),
    ],
    ids=["empty", "unmatched-only", "single-bit", "overlapping-bits", "manual"],
)
def test_count_per_registry_splits_a_bitmask_histogram(
    mask_counts: dict[int, int], expected: dict[Registry, int]
) -> None:
    assert count_per_registry(mask_counts) == expected
