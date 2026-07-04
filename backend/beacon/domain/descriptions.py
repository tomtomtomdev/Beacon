"""Job-description normalization and the content hash that gates re-classification.

Changing this normalization changes every content_hash — do not touch without
a backfill plan (see CLAUDE.md "Data correctness notes").
"""

import hashlib
import html
import re

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def normalize_description(raw: str) -> str:
    """ATS APIs ship escaped HTML; reduce it to plain, whitespace-collapsed text."""
    markup = html.unescape(raw)
    text = _TAG.sub(" ", markup)
    text = html.unescape(text)  # entities inside text survive the first pass
    return _WHITESPACE.sub(" ", text).strip()


def content_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
