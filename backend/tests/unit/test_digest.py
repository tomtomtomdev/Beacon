from beacon.domain.digest import Digest, DigestGroup, DigestLine, build_messages


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
