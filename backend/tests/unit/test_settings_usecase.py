from beacon.application.settings import (
    effective_telegram_config,
    send_test_message,
    update_telegram_config,
)
from beacon.domain.digest import Digest
from beacon.domain.notification import TelegramConfig


class FakeSettingsRepo:
    def __init__(self, config: TelegramConfig | None = None) -> None:
        self.config = config or TelegramConfig()

    def get_telegram_config(self) -> TelegramConfig:
        return self.config

    def set_telegram_config(self, config: TelegramConfig) -> None:
        self.config = config


class SpyNotifier:
    def __init__(self) -> None:
        self.sent: list[Digest] = []

    async def send(self, digest: Digest) -> None:
        self.sent.append(digest)


def test_effective_config_layers_stored_over_env() -> None:
    repo = FakeSettingsRepo(TelegramConfig(bot_token="db-token", chat_id=None))
    env = TelegramConfig(bot_token="env-token", chat_id="env-chat")

    effective = effective_telegram_config(repo, env)

    assert effective == TelegramConfig(bot_token="db-token", chat_id="env-chat")


def test_update_persists_both_fields() -> None:
    repo = FakeSettingsRepo()

    result = update_telegram_config(repo, chat_id="4242", bot_token="123:secret")

    assert result == TelegramConfig(bot_token="123:secret", chat_id="4242")
    assert repo.config == result


def test_update_with_none_token_keeps_the_stored_token() -> None:
    # The UI never re-sends the secret; a chat_id-only save must not wipe the token.
    repo = FakeSettingsRepo(TelegramConfig(bot_token="kept", chat_id="1"))

    result = update_telegram_config(repo, chat_id="2", bot_token=None)

    assert result == TelegramConfig(bot_token="kept", chat_id="2")


def test_update_with_empty_token_clears_the_stored_token() -> None:
    repo = FakeSettingsRepo(TelegramConfig(bot_token="old", chat_id="1"))

    result = update_telegram_config(repo, chat_id="1", bot_token="")

    assert result.bot_token is None


async def test_send_test_message_delivers_a_nonempty_digest() -> None:
    notifier = SpyNotifier()

    await send_test_message(notifier)

    assert len(notifier.sent) == 1
    assert not notifier.sent[0].is_empty()
