from beacon.domain.digest import (
    Digest,
    DigestGroup,
    DigestLine,
    HealthAlert,
    RegistryStale,
    build_messages,
)


def _line(title: str, *, country: str | None = "SE", tier: str = "registry_inferred") -> DigestLine:
    return DigestLine(
        title=title,
        company="Spotify",
        country=country,
        tier=tier,
        url=f"https://example.test/{title}",
        reason=f"ios · {country} · {tier}",
    )


def test_digest_format_one_grouped_message() -> None:
    digest = Digest(
        groups=(
            DigestGroup(
                "Senior iOS", (_line("iOS Engineer"), _line("Staff iOS", tier="explicit_yes"))
            ),
            DigestGroup("Backend NL", (_line("Backend Engineer", country="NL"),)),
        )
    )

    messages = build_messages(digest, max_chars=4096)

    assert len(messages) == 1
    text = messages[0]
    # Grouped by search name.
    assert "Senior iOS" in text
    assert "Backend NL" in text
    # Every line carries title + company + country + tier + url.
    for fragment in ("iOS Engineer", "Spotify", "SE", "registry_inferred", "explicit_yes"):
        assert fragment in text
    assert "https://example.test/iOS Engineer" in text
    assert "https://example.test/Backend Engineer" in text


def test_digest_splits_when_over_max_without_breaking_a_line() -> None:
    lines = tuple(_line(f"Engineer {i}") for i in range(40))
    digest = Digest(groups=(DigestGroup("Big search", lines),))

    messages = build_messages(digest, max_chars=300)

    assert len(messages) > 1
    assert all(len(m) <= 300 for m in messages)
    # No entry is cut in half: every posting URL survives intact as its own line, once.
    url_lines = [
        line.strip()
        for message in messages
        for line in message.splitlines()
        if line.strip().startswith("https://example.test/Engineer")
    ]
    assert sorted(url_lines) == sorted(f"https://example.test/Engineer {i}" for i in range(40))


def test_empty_digest_produces_no_messages() -> None:
    assert build_messages(Digest(groups=()), max_chars=4096) == []
    assert Digest(groups=(DigestGroup("Empty", ()),)).is_empty()


def test_health_alerts_lead_the_digest_with_company_reason_and_since() -> None:
    digest = Digest(
        groups=(),
        health_alerts=(
            HealthAlert(company="crypto", reason="gone", since="2026-06-01"),
            HealthAlert(company="smartnews", reason="schema_drift", since="never"),
        ),
        stale_registries=(RegistryStale(registry="UK", fetched_at="2026-05-01"),),
    )

    messages = build_messages(digest, max_chars=4096)

    assert len(messages) == 1
    text = messages[0]
    for fragment in ("crypto", "gone", "2026-06-01", "smartnews", "schema_drift", "never"):
        assert fragment in text
    assert "UK" in text and "2026-05-01" in text


def test_health_only_digest_is_not_empty_and_sends() -> None:
    # A quarantine with no new job matches must still notify — silent decay is the failure mode.
    digest = Digest(
        groups=(), health_alerts=(HealthAlert(company="crypto", reason="gone", since="never"),)
    )

    assert digest.is_empty() is False
    assert len(build_messages(digest, max_chars=4096)) == 1


def test_stale_registry_alone_is_not_empty() -> None:
    digest = Digest(
        groups=(), stale_registries=(RegistryStale(registry="UK", fetched_at="2026-01-01"),)
    )

    assert digest.is_empty() is False
