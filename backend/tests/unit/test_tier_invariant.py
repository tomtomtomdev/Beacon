"""The invariant CLAUDE.md calls out explicitly: registry_inferred can never appear on
a company with empty registry_flags. Guarded here with hypothesis over random flags."""

from hypothesis import given
from hypothesis import strategies as st

from beacon.domain.sponsorship import SponsorTier, resolve_tier

_ANY_FLAGS = st.integers(min_value=0, max_value=255)


@given(flags=_ANY_FLAGS)
def test_registry_inferred_implies_nonzero_flags(flags: int) -> None:
    if resolve_tier(None, flags) is SponsorTier.REGISTRY_INFERRED:
        assert flags != 0


@given(flags=_ANY_FLAGS, text=st.sampled_from([SponsorTier.EXPLICIT_YES, SponsorTier.EXPLICIT_NO]))
def test_explicit_text_beats_any_registry_flags(flags: int, text: SponsorTier) -> None:
    assert resolve_tier(text, flags) is text
