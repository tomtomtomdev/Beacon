-- Version the Tier-1 score cache (§11 12c).
--
-- job_match_scores was gated on content_hash alone, so a change to the *scoring code* never
-- invalidated a row: the SWIFT homograph guard and the skill-coverage floor both shipped on
-- 2026-08-26, hours after the cache was warmed, and no cached score ever saw them.
--
-- Existing rows default to 0, which no SCORING_VERSION will ever equal (it starts at 1), so
-- the whole pre-versioning cache invalidates itself on next read. No backfill, no DELETE.
ALTER TABLE job_match_scores ADD COLUMN scoring_version INTEGER NOT NULL DEFAULT 0;
