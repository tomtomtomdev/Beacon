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
    }


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
