"""Real migrations applied to a tmp SQLite file must produce the full SPEC §7 schema."""

import sqlite3

import pytest


def columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


def test_companies_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "companies") == {
        "id",
        "name",
        "ats_type",
        "ats_slug",
        "country_hq",
        "registry_flags",
        "match_confidence",
        "match_evidence",
        "priority",
        "active",
        "consecutive_failures",
        "last_success_at",
        "health",
        "quarantine_reason",
    }


def test_jobs_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "jobs") == {
        "id",
        "canonical_id",
        "company_id",
        "source_id",
        "external_id",
        "title",
        "description",
        "url",
        "location_raw",
        "country",
        "city",
        "remote_scope",
        "categories",
        "level",
        "sponsor_tier",
        "sponsor_evidence",
        "content_hash",
        "posted_at",
        "first_seen_at",
        "last_seen_at",
        "closed_at",
        "user_status",
        "consecutive_misses",
    }


def test_registries_meta_bookkeeping_table_exists(db: sqlite3.Connection) -> None:
    assert columns(db, "registries_meta") == {"registry", "fetched_at", "row_count"}


def test_saved_searches_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "saved_searches") == {
        "id",
        "name",
        "filters_json",
        "notify_channel",
        "last_run_at",
    }


def test_seen_matches_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "seen_matches") == {
        "search_id",
        "job_canonical_id",
        "notified_at",
        "match_reason",
    }


def test_app_settings_key_value_table_exists(db: sqlite3.Connection) -> None:
    assert columns(db, "app_settings") == {"key", "value"}


def test_llm_usage_bookkeeping_table_exists(db: sqlite3.Connection) -> None:
    assert columns(db, "llm_usage") == {"month", "call_count"}


def test_countries_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "countries") == {
        "code",
        "name",
        "visa_summary",
        "pr_summary",
        "citizenship_summary",
        "registry_name",
        "priority_tier",
        "verified_at",
        "source_url",
    }


def test_resumes_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "resumes") == {
        "id",
        "label",
        "source_text",
        "profile_json",
        "resume_hash",
        "active",
        "created_at",
    }


def test_job_match_scores_table_has_full_spec_schema(db: sqlite3.Connection) -> None:
    assert columns(db, "job_match_scores") == {
        "resume_hash",
        "job_canonical_id",
        "overall",
        "skills_score",
        "level_score",
        "sponsor_score",
        "matched_skills",
        "missing_skills",
        "content_hash",
        "computed_at",
    }


def test_resume_hash_is_unique(db: sqlite3.Connection) -> None:
    insert = (
        "INSERT INTO resumes (label, source_text, profile_json, resume_hash, created_at)"
        " VALUES ('CV', 'text', '{}', 'abc', 't')"
    )
    db.execute(insert)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert)


def test_jobs_reject_duplicate_source_external_id(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO companies (name, ats_type, ats_slug, country_hq, priority)"
        " VALUES ('Tines', 'greenhouse', 'tines', 'IE', 2)"
    )
    insert = (
        "INSERT INTO jobs (company_id, source_id, external_id, title, description, url,"
        " content_hash, first_seen_at, last_seen_at)"
        " VALUES (1, 'greenhouse', '42', 'Engineer', 'd', 'https://x', 'h', 't', 't')"
    )
    db.execute(insert)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert)


def test_company_names_are_unique(db: sqlite3.Connection) -> None:
    insert = (
        "INSERT INTO companies (name, ats_type, ats_slug, country_hq, priority)"
        " VALUES ('Tines', 'greenhouse', 'tines', 'IE', 2)"
    )
    db.execute(insert)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert)
