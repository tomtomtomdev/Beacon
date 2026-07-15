-- Slice 12 (§11). Resume-fit scoring: uploaded resumes + the Tier-1 heuristic score cache.
--
-- resumes: one row per uploaded resume, deduped by resume_hash = sha256(source_text).
-- Exactly one row is active at a time (enforced by the app, not a constraint — SQLite has no
-- partial-unique that fits cleanly). profile_json is the serialized ResumeProfile
-- (skills/categories/level/years/target_countries), so the profile survives a restart without
-- re-parsing. Matching is a read-side concern layered on canonical jobs; nothing here touches
-- the ingest/classify pipeline (golden rule 1).
--
-- job_match_scores: caches one resume<->job heuristic score keyed (resume_hash,
-- job_canonical_id). content_hash gates the cache exactly like classification — a re-poll of
-- an unchanged posting reuses its score; a changed posting (new content_hash) recomputes only
-- itself. llm_rationale is the optional Tier-2 deep-match text (slice 12e), null until asked.

CREATE TABLE resumes (
    id           INTEGER PRIMARY KEY,
    label        TEXT NOT NULL,
    source_text  TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    resume_hash  TEXT NOT NULL UNIQUE,
    active       INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE job_match_scores (
    resume_hash      TEXT NOT NULL,
    job_canonical_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    overall          INTEGER NOT NULL,
    skills_score     INTEGER NOT NULL,
    level_score      INTEGER NOT NULL,
    sponsor_score    INTEGER NOT NULL,
    matched_skills   TEXT NOT NULL,
    missing_skills   TEXT NOT NULL,
    llm_rationale    TEXT,
    content_hash     TEXT NOT NULL,
    computed_at      TEXT NOT NULL,
    PRIMARY KEY (resume_hash, job_canonical_id)
);
