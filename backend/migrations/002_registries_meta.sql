-- Slice 2. The companies/jobs columns for sponsorship already exist (migration 001);
-- this migration only adds bookkeeping for registry refreshes so the digest can nag
-- when a snapshot goes stale (SPEC §7: fetched_at > 45 days → warning).

CREATE TABLE registries_meta (
    registry   TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    row_count  INTEGER NOT NULL
);
