-- Full SPEC §7 schema for companies and jobs. All columns created now;
-- classifier (slice 3), sponsorship (slices 2/6), dedup (slice 5), user status
-- (slice 5.5) and source health (slice 11) fill them later.

CREATE TABLE companies (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL UNIQUE,
    ats_type             TEXT NOT NULL,
    ats_slug             TEXT NOT NULL,
    country_hq           TEXT NOT NULL,
    registry_flags       INTEGER NOT NULL DEFAULT 0,
    match_confidence     REAL,
    priority             INTEGER NOT NULL DEFAULT 3,
    active               INTEGER NOT NULL DEFAULT 1,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_success_at      TEXT,
    health               TEXT NOT NULL DEFAULT 'ok',
    quarantine_reason    TEXT
);

CREATE TABLE jobs (
    id               INTEGER PRIMARY KEY,
    canonical_id     INTEGER REFERENCES jobs(id),
    company_id       INTEGER NOT NULL REFERENCES companies(id),
    source_id        TEXT NOT NULL,
    external_id      TEXT NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL,
    url              TEXT NOT NULL,
    location_raw     TEXT NOT NULL DEFAULT '',
    country          TEXT,
    city             TEXT,
    remote_scope     TEXT,
    categories       TEXT,
    level            TEXT,
    sponsor_tier     TEXT NOT NULL DEFAULT 'unknown',
    sponsor_evidence TEXT,
    content_hash     TEXT NOT NULL,
    posted_at        TEXT,
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    closed_at        TEXT,
    user_status      TEXT NOT NULL DEFAULT 'new',
    UNIQUE (source_id, external_id)
);

CREATE INDEX idx_jobs_country ON jobs (country);
CREATE INDEX idx_jobs_posted_at ON jobs (posted_at);
CREATE INDEX idx_jobs_company ON jobs (company_id);
