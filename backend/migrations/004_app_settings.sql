-- Slice 8 (settings). User-editable runtime config as a key/value store, set via the
-- Settings UI. First keys: telegram_bot_token, telegram_chat_id. DB-set values override
-- the BEACON_TELEGRAM_* env fallback at notify time (see domain TelegramConfig.merge).

CREATE TABLE app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
