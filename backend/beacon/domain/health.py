"""Source health as a first-class state (SPEC §7).

Sources move, get acquired, and take boards offline; a poll failure is a state, never data.
These pure transitions turn a stream of poll outcomes into a health verdict the pipeline
reads (skip quarantined) and the digest reports. The repo persists a SourceHealth to the
companies health columns; nothing here does IO."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


class FailureKind(StrEnum):
    """Why a poll failed — drives the quarantine threshold and the digest reason line."""

    GONE = "gone"  # 404/410: slug moved/removed — needs a human, quarantine fast
    UNREACHABLE = "unreachable"  # 5xx / timeout / transport: transient, be patient
    SCHEMA_DRIFT = "schema_drift"  # fetched but couldn't parse: API changed shape


class Health(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"  # failing, but under its quarantine threshold — still polled
    QUARANTINED = "quarantined"  # skipped by the regular poll; only the weekly probe retries


# Consecutive-failure thresholds per kind (SPEC §7). A moved slug or a shape change both need
# a human, so quarantine after 3; a transient 5xx/timeout streak is given a patient 10.
GONE_THRESHOLD = 3
SCHEMA_DRIFT_THRESHOLD = 3
UNREACHABLE_THRESHOLD = 10

_THRESHOLDS: dict[FailureKind, int] = {
    FailureKind.GONE: GONE_THRESHOLD,
    FailureKind.UNREACHABLE: UNREACHABLE_THRESHOLD,
    FailureKind.SCHEMA_DRIFT: SCHEMA_DRIFT_THRESHOLD,
}


@dataclass(frozen=True, slots=True)
class SourceHealth:
    """A company's polling health. `reason` names the current failure streak's kind — set
    while degraded or quarantined (so the digest/UI can say "2 failures · 5xx"), None when
    healthy. Persisted to companies.{consecutive_failures,health,quarantine_reason,last_success_at}."""

    consecutive_failures: int = 0
    health: Health = Health.OK
    reason: FailureKind | None = None
    last_success_at: datetime | None = None


def record_failure(state: SourceHealth, kind: FailureKind) -> SourceHealth:
    """One more consecutive failure of this kind: degrade, or quarantine once the streak
    reaches the kind's threshold. last_success_at is left as-is (a failure is not a success)."""
    failures = state.consecutive_failures + 1
    health = Health.QUARANTINED if failures >= _THRESHOLDS[kind] else Health.DEGRADED
    return replace(state, consecutive_failures=failures, health=health, reason=kind)


def record_success(state: SourceHealth, *, now: datetime) -> SourceHealth:
    """A clean poll: reset the streak to zero, clear the reason, stamp the success time."""
    return replace(
        state,
        consecutive_failures=0,
        health=Health.OK,
        reason=None,
        last_success_at=now,
    )


def should_poll(state: SourceHealth) -> bool:
    """The regular poll skips quarantined sources (no log spam, no wasted requests); only the
    weekly probe retries them. Degraded sources are still polled — they might recover."""
    return state.health is not Health.QUARANTINED
