"""Source-health state machine (SPEC §7): pure transitions over a company's polling health.

Thresholds are per failure-kind — a moved slug (gone) or a shape change (schema_drift)
needs a human fast (quarantine after 3); transient 5xx/timeouts get a patient 10."""

from datetime import UTC, datetime

import pytest

from beacon.domain.health import (
    GONE_THRESHOLD,
    SCHEMA_DRIFT_THRESHOLD,
    UNREACHABLE_THRESHOLD,
    FailureKind,
    Health,
    SourceHealth,
    record_failure,
    record_success,
    should_poll,
)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def test_fresh_health_is_ok_and_pollable() -> None:
    state = SourceHealth()

    assert state.health is Health.OK
    assert state.consecutive_failures == 0
    assert state.reason is None
    assert should_poll(state) is True


@pytest.mark.parametrize(
    ("kind", "threshold"),
    [
        (FailureKind.GONE, GONE_THRESHOLD),
        (FailureKind.SCHEMA_DRIFT, SCHEMA_DRIFT_THRESHOLD),
        (FailureKind.UNREACHABLE, UNREACHABLE_THRESHOLD),
    ],
    ids=["gone-3", "schema_drift-3", "unreachable-10"],
)
def test_repeated_failures_degrade_then_quarantine_at_the_kinds_threshold(
    kind: FailureKind, threshold: int
) -> None:
    state = SourceHealth()

    for expected in range(1, threshold):
        state = record_failure(state, kind)
        assert state.consecutive_failures == expected
        assert state.health is Health.DEGRADED
        assert state.reason is kind
        assert should_poll(state) is True

    state = record_failure(state, kind)  # the threshold-th failure

    assert state.consecutive_failures == threshold
    assert state.health is Health.QUARANTINED
    assert state.reason is kind
    assert should_poll(state) is False


def test_unreachable_below_gone_threshold_does_not_quarantine() -> None:
    # A transient 5xx streak must stay patient — 3 unreachable failures is not a quarantine.
    state = SourceHealth()
    for _ in range(GONE_THRESHOLD):
        state = record_failure(state, FailureKind.UNREACHABLE)

    assert state.health is Health.DEGRADED
    assert should_poll(state) is True


def test_success_resets_the_streak_and_stamps_the_time() -> None:
    state = SourceHealth()
    for _ in range(GONE_THRESHOLD):
        state = record_failure(state, FailureKind.GONE)
    assert state.health is Health.QUARANTINED

    restored = record_success(state, now=NOW)

    assert restored.consecutive_failures == 0
    assert restored.health is Health.OK
    assert restored.reason is None
    assert restored.last_success_at == NOW
    assert should_poll(restored) is True


def test_success_mid_streak_clears_before_quarantine() -> None:
    state = SourceHealth()
    state = record_failure(state, FailureKind.GONE)
    state = record_failure(state, FailureKind.GONE)  # one short of quarantine

    state = record_success(state, now=NOW)
    state = record_failure(state, FailureKind.GONE)  # streak restarts at 1

    assert state.consecutive_failures == 1
    assert state.health is Health.DEGRADED
