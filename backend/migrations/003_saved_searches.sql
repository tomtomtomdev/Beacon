-- Slice 8. Saved searches and the notify-once ledger (SPEC §7).
-- filters_json is the serialized domain SearchFilters (see saved_search.filters_to_json).
-- seen_matches records every (search, canonical job) already sent so a match is never
-- notified twice; match_reason captures which filters fired, for the digest line.

CREATE TABLE saved_searches (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    filters_json   TEXT NOT NULL,
    notify_channel TEXT NOT NULL DEFAULT 'telegram',
    last_run_at    TEXT
);

CREATE TABLE seen_matches (
    search_id        INTEGER NOT NULL REFERENCES saved_searches(id) ON DELETE CASCADE,
    job_canonical_id INTEGER NOT NULL REFERENCES jobs(id),
    notified_at      TEXT NOT NULL,
    match_reason     TEXT NOT NULL,
    PRIMARY KEY (search_id, job_canonical_id)
);
