"""StdoutNotifier — prints the digest. The zero-config fallback when no Telegram
bot token/chat_id is set, and handy for local acceptance runs."""

from beacon.domain.digest import Digest, build_messages

# No transport limit on a terminal; a generous cap keeps a runaway digest readable.
_STDOUT_MAX_CHARS = 100_000


class StdoutNotifier:
    async def send(self, digest: Digest) -> None:
        for message in build_messages(digest, max_chars=_STDOUT_MAX_CHARS):
            print(message)
