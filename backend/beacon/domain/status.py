"""Per-job user status — the daily-scan lifecycle. This enum is the single source
of truth for valid status values (API validation, list-filter defaults)."""

from enum import StrEnum


class UserStatus(StrEnum):
    NEW = "new"
    SEEN = "seen"
    HIDDEN = "hidden"
    STARRED = "starred"


# The default /jobs view hides only what the user explicitly hid; new/seen/starred
# all stay visible. Sponsorship-style soft signal: nothing else is filtered by default.
DEFAULT_VISIBLE: frozenset[UserStatus] = frozenset(UserStatus) - {UserStatus.HIDDEN}
