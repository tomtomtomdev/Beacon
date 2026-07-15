"""PlainTextResumeParser — the always-available, zero-dependency resume parse path (§11)."""

import pytest

from beacon.adapters.resume.plaintext import PlainTextResumeParser


def test_pasted_text_is_returned_unchanged() -> None:
    parser = PlainTextResumeParser()

    assert (
        parser.parse("Senior iOS Engineer\n8 years Swift", "text")
        == "Senior iOS Engineer\n8 years Swift"
    )


def test_txt_upload_bytes_are_decoded_as_utf8() -> None:
    parser = PlainTextResumeParser()

    assert parser.parse("Café résumé — Swift".encode(), "txt") == "Café résumé — Swift"


def test_unsupported_kind_is_rejected() -> None:
    parser = PlainTextResumeParser()

    with pytest.raises(ValueError, match="pdf"):
        parser.parse(b"%PDF-1.7 ...", "pdf")
