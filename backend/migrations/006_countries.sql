-- Slice 10. Country & visa reference data (SPEC §4). Seeded from the domain constant
-- COUNTRY_REFERENCE (domain/visa.py) at startup — a queryable projection of that source
-- of truth. Each row carries verified_at + source_url for manual re-verification, since
-- the figures are as-known and change over time (SPEC §4). code is ISO-3166-1 alpha-2 so
-- a job's parsed country joins straight to its relocation reference.

CREATE TABLE countries (
    code                TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    visa_summary        TEXT NOT NULL,
    pr_summary          TEXT NOT NULL,
    citizenship_summary TEXT NOT NULL,
    registry_name       TEXT,
    priority_tier       TEXT NOT NULL,
    verified_at         TEXT NOT NULL,
    source_url          TEXT NOT NULL
);
