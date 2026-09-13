"""The steerable boards' `ROLE_QUERIES` tuples, as data (slice 16b).

Himalayas and MyCareersFuture are the only two sources that reach a role family by *asking*
for it rather than by polling one employer's board, which makes their query tuples the
cheapest lever on supply. These tests read the tuples, never a copy of them: widening
coverage is a data edit plus a row here, exactly as extending the category vocabulary is.

The required tokens differ per board because the boards measurably differ — see the
2026-09-13 per-query probe in PROGRESS: "swift engineer" returns 37 employers on Himalayas
and *zero rows* on MyCareersFuture, so requiring it of both would pin a dead query into a
poll. A board is required to cover the tokens its own search actually answers.
"""

import pytest

from beacon.adapters.sources.himalayas import ROLE_QUERIES as HIMALAYAS_QUERIES
from beacon.adapters.sources.mycareersfuture import ROLE_QUERIES as MCF_QUERIES
from beacon.domain.vocabulary import extract_skills

_ALL_BOARDS = pytest.mark.parametrize(
    "queries",
    [HIMALAYAS_QUERIES, MCF_QUERIES],
    ids=["himalayas", "mycareersfuture"],
)


@pytest.mark.parametrize(
    ("queries", "token"),
    [
        pytest.param(HIMALAYAS_QUERIES, "ios", id="himalayas-ios"),
        pytest.param(HIMALAYAS_QUERIES, "swift", id="himalayas-swift"),
        pytest.param(MCF_QUERIES, "ios", id="mycareersfuture-ios"),
    ],
)
def test_role_queries_cover_the_ios_vocabulary(queries: tuple[str, ...], token: str) -> None:
    covered = {skill for query in queries for skill in extract_skills(query)}

    assert token in covered


@_ALL_BOARDS
def test_no_role_query_is_a_bare_generic_term(queries: tuple[str, ...]) -> None:
    """A one-word query is a firehose, not a steer — the slice-14 lesson about unsteerable
    sources applies to over-broad queries too. Bare "mobile" was rejected for exactly this."""
    bare = [query for query in queries if len(query.split()) < 2]

    assert bare == []
