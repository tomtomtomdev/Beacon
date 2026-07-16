-- 009: the Tier-2 deep-match went deterministic (PROGRESS decision 2026-07-16) — the
-- rationale is pure wording recomputed on demand, so the stored-LLM-text column and any
-- stale rows in it go away. job_match_scores keeps caching Tier-1 scores only.
ALTER TABLE job_match_scores DROP COLUMN llm_rationale;
