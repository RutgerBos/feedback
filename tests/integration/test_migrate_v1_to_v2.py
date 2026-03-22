"""Integration tests for scripts/migrate_v1_to_v2.py against real MongoDB."""

import sys
import os
from datetime import datetime, UTC
from uuid import uuid4

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.migrate_v1_to_v2 import migrate


@pytest.fixture
def mongo_client():
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    yield client
    client.drop_database("test_migrate")
    client.close()


@pytest.fixture
def clean_db(mongo_client):
    db = mongo_client["test_migrate"]
    db.stories.delete_many({})
    yield db


def _v1_doc(doc_id: str | None = None, with_metadata: bool = False) -> dict:
    base = {
        "_id": doc_id or str(uuid4()),
        "story_text": "Some story text for testing purposes.",
        "triads": [
            {"triad_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
            {"triad_id": "understanding_quality", "coordinates": {"x": 0.7, "y": 0.2}},
        ],
        "metadata": None,
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
        "processing_status": "processed",
        "entity_status": "pending",
        "sentiment_status": "pending",
        "entities": [],
        "themes": [],
        "sentiment": None,
    }
    if with_metadata:
        base["metadata"] = {
            "user_pseudonym": "tester",
            "department": "Engineering",
            "role": "Lead",
            "tool_context": "CI/CD",
        }
    return base


def _v2_doc(doc_id: str | None = None) -> dict:
    return {
        "_id": doc_id or str(uuid4()),
        "story_text": "Already migrated story.",
        "schema_version": 2,
        "triads": [],
        "metadata": None,
        "signification": {
            "headline": None,
            "responses": [{"kind": "triad", "signifier_id": "t1", "coordinates": {"x": 0.5, "y": 0.5}}],
        },
        "context": None,
        "participant": None,
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
        "processing_status": "processed",
        "entity_status": "pending",
        "sentiment_status": "pending",
        "entities": [],
        "themes": [],
        "sentiment": None,
    }


# ── Test 1: V1 documents are migrated and readable as V2 ─────────────────────


def test_migrate_updates_v1_docs(clean_db):
    doc_id = str(uuid4())
    clean_db.stories.insert_one(_v1_doc(doc_id))

    migrated, skipped = migrate(clean_db)

    assert migrated == 1
    assert skipped == 0

    updated = clean_db.stories.find_one({"_id": doc_id})
    assert updated["schema_version"] == 2
    assert updated["triads"] == []
    assert updated["metadata"] is None
    assert len(updated["signification"]["responses"]) == 2
    assert updated["signification"]["responses"][0]["kind"] == "triad"
    assert updated["signification"]["responses"][0]["signifier_id"] == "workflow_nature"


# ── Test 2: already-V2 documents are skipped ──────────────────────────────────


def test_migrate_skips_v2_docs(clean_db):
    doc_id = str(uuid4())
    clean_db.stories.insert_one(_v2_doc(doc_id))

    migrated, skipped = migrate(clean_db)

    assert migrated == 0
    assert skipped == 0  # V2 docs not even matched by query


# ── Test 3: idempotent — running twice produces same result ───────────────────


def test_migrate_is_idempotent(clean_db):
    clean_db.stories.insert_one(_v1_doc())

    migrated1, _ = migrate(clean_db)
    migrated2, _ = migrate(clean_db)

    assert migrated1 == 1
    assert migrated2 == 0  # Already V2 on second run


# ── Test 4: metadata is split into context + participant ──────────────────────


def test_migrate_splits_metadata(clean_db):
    doc_id = str(uuid4())
    clean_db.stories.insert_one(_v1_doc(doc_id, with_metadata=True))

    migrate(clean_db)

    updated = clean_db.stories.find_one({"_id": doc_id})
    assert updated["context"] == {
        "department": "Engineering",
        "role": "Lead",
        "tool_context": "CI/CD",
    }
    assert updated["participant"] == {"user_pseudonym": "tester"}
    assert updated["metadata"] is None


# ── Test 5: dry_run does not write to DB ──────────────────────────────────────


def test_migrate_dry_run_does_not_write(clean_db):
    doc_id = str(uuid4())
    clean_db.stories.insert_one(_v1_doc(doc_id))

    migrated, _ = migrate(clean_db, dry_run=True)

    assert migrated == 1  # counted

    untouched = clean_db.stories.find_one({"_id": doc_id})
    assert untouched.get("schema_version") != 2  # not written


# ── Test 6: mixed V1 and V2 — only V1 are touched ────────────────────────────


def test_migrate_mixed_collection(clean_db):
    v1_id = str(uuid4())
    v2_id = str(uuid4())
    clean_db.stories.insert_many([_v1_doc(v1_id), _v2_doc(v2_id)])

    migrated, _ = migrate(clean_db)

    assert migrated == 1

    v1_updated = clean_db.stories.find_one({"_id": v1_id})
    v2_unchanged = clean_db.stories.find_one({"_id": v2_id})

    assert v1_updated["schema_version"] == 2
    assert v2_unchanged["schema_version"] == 2
    # V2 doc's signification should still have original single response
    assert len(v2_unchanged["signification"]["responses"]) == 1
