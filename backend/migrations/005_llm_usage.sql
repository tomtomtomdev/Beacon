-- Slice 9. Hard monthly cap on LLM classifier calls (SPEC §9 cost control). One row per
-- month, keyed "YYYY-MM" in the app's LOCAL_TZ (Asia/Jakarta); call_count is the number of
-- LLM calls reserved that month. "registries_meta-style" bookkeeping: tiny and dedicated.

CREATE TABLE llm_usage (
    month      TEXT PRIMARY KEY,
    call_count INTEGER NOT NULL DEFAULT 0
);
