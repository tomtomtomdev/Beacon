"""The new-match digest: a channel-agnostic structure plus a pure text renderer.

The domain owns *what* a digest says and how it packs into fixed-size messages;
each Notifier adapter owns the size limit of its channel (Telegram's is 4096).
Keeping the packer pure and parameterized makes the split unit-testable without HTTP."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DigestLine:
    """One matched job as it appears in the digest."""

    title: str
    company: str
    country: str | None
    tier: str
    url: str
    reason: str  # which of the search's filters fired — see saved_search.match_reason


@dataclass(frozen=True, slots=True)
class DigestGroup:
    """All of one saved search's new matches, under its name."""

    search_name: str
    lines: tuple[DigestLine, ...]


@dataclass(frozen=True, slots=True)
class Digest:
    groups: tuple[DigestGroup, ...]

    def is_empty(self) -> bool:
        return not any(group.lines for group in self.groups)


def _render_line(line: DigestLine) -> str:
    country = line.country or "—"
    return (
        f"• {line.title} — {line.company} · {country} · {line.tier}\n"
        f"  why: {line.reason}\n"
        f"  {line.url}"
    )


def _render_header(group: DigestGroup) -> str:
    return f"🔔 {group.search_name} ({len(group.lines)} new)"


def _units(digest: Digest) -> list[str]:
    """Atomic blocks to pack. A group's header always travels with its first entry so a
    header is never orphaned at the end of a message; later entries pack on their own."""
    units: list[str] = []
    for group in digest.groups:
        if not group.lines:
            continue
        entries = [_render_line(line) for line in group.lines]
        units.append(f"{_render_header(group)}\n{entries[0]}")
        units.extend(entries[1:])
    return units


def _hard_split(text: str, max_chars: int) -> list[str]:
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def build_messages(digest: Digest, *, max_chars: int) -> list[str]:
    """Render the digest into messages of at most max_chars, never breaking an entry
    (a single entry longer than max_chars is the only thing hard-split)."""
    messages: list[str] = []
    current = ""
    for unit in _units(digest):
        candidate = f"{current}\n\n{unit}" if current else unit
        if current and len(candidate) > max_chars:
            messages.append(current)
            current = unit
        else:
            current = candidate
        if len(current) > max_chars:  # a lone oversize unit
            *whole, current = _hard_split(current, max_chars)
            messages.extend(whole)
    if current:
        messages.append(current)
    return messages
