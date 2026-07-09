from datetime import UTC, datetime, timedelta

import pytest

from beacon.domain.registry import (
    REGISTRY_STALE_AFTER_DAYS,
    Registry,
    RegistryCompany,
    RegistryMeta,
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


def test_bitmask_members_are_uk_nl_us_manual_only() -> None:
    # SPEC §5.3: no SE bit exists — the Swedish scheme was discontinued.
    assert {r.name for r in Registry} == {"UK", "NL", "US", "MANUAL"}


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
    ],
    ids=["none", "uk", "manual", "uk-nl", "all"],
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
