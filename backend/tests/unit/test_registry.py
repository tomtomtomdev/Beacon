from beacon.domain.registry import Registry, RegistryCompany


def test_bitmask_members_are_uk_nl_us_manual_only() -> None:
    # SPEC §5.3: no SE bit exists — the Swedish scheme was discontinued.
    assert {r.name for r in Registry} == {"UK", "NL", "US", "MANUAL"}


def test_flags_compose_and_test_by_bit() -> None:
    flags = Registry.UK | Registry.NL

    assert flags & Registry.UK
    assert flags & Registry.NL
    assert not flags & Registry.US
    assert int(flags) == int(Registry.UK) + int(Registry.NL)


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
