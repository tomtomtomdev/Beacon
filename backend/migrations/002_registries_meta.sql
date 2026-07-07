-- Slice 2. The companies/jobs columns for sponsorship already exist (migration 001);
-- this migration only adds bookkeeping for registry refreshes so the digest can nag
-- when a snapshot goes stale (SPEC §7: fetched_at > 45 days → warning).

CREATE TABLE registries_meta (
    registry   TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    row_count  INTEGER NOT NULL
);

-- SPEC §7's companies schema omitted an evidence column, but SPEC §5.3 / PLAN slice 2
-- require the MANUAL flag to carry an evidence note + date, and the JobDetail drawer
-- (slice 10) will show which registries matched. One free-text column serves both the
-- fuzzy-match audit trail ("UK Skilled Worker; NL KvK …") and MANUAL notes.
ALTER TABLE companies ADD COLUMN match_evidence TEXT;
