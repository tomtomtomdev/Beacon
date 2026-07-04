from beacon.domain.descriptions import content_hash, normalize_description


def test_normalize_unescapes_html_strips_tags_and_collapses_whitespace() -> None:
    # Greenhouse `content` is HTML-escaped HTML, exactly like this.
    raw = (
        "&lt;div class=&quot;content-intro&quot;&gt;&lt;p&gt;Tines powers the world&#39;s "
        "workflows.&lt;/p&gt;&lt;/div&gt;\n&lt;p&gt;  Apply   now &amp;amp; join us.&lt;/p&gt;"
    )

    assert normalize_description(raw) == "Tines powers the world's workflows. Apply now & join us."


def test_content_hash_is_stable_for_cosmetic_markup_changes() -> None:
    a = "&lt;p&gt;Build things.&lt;/p&gt;"
    b = "&lt;div&gt;&lt;p&gt;Build   things.&lt;/p&gt;&lt;/div&gt;"

    assert content_hash(normalize_description(a)) == content_hash(normalize_description(b))


def test_content_hash_differs_when_text_differs() -> None:
    assert content_hash("Build things.") != content_hash("Break things.")
