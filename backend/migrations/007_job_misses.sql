-- Slice 10. Closed-posting sweep. Per-job counter of consecutive *successful* polls of its
-- source in which the posting was absent from the response. When it reaches CLOSE_AFTER_MISSES
-- the job's closed_at is set (kept, greyed out — SPEC §7). Failed polls never run the sweep, so
-- a 404'd board can never mass-close its jobs. Not in the SPEC §7 jobs column list; added here
-- for this lifecycle policy, like slice-2's match_evidence.

ALTER TABLE jobs ADD COLUMN consecutive_misses INTEGER NOT NULL DEFAULT 0;
