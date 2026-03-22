"""Integration tests for scripts/reconcile_neo4j.py against real MongoDB and Neo4j."""

import sys
import os
from datetime import datetime, UTC

import pytest
from pymongo import MongoClient
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.reconcile_neo4j import reconcile


MONGO_URL = "mongodb://admin:password@localhost:27017/"
NEO4J_URL = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "password")


def _neo4j_is_reachable() -> bool:
    try:
        driver = GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)
        driver.verify_connectivity()
        driver.close()
        return True
    except (ServiceUnavailable, Exception):
        return False


@pytest.fixture(scope="module", autouse=True)
def require_neo4j():
    if not _neo4j_is_reachable():
        pytest.skip("Neo4j not reachable at localhost:7687")


TEST_PREFIX = "test-reconcile-"


@pytest.fixture
def mongo_db():
    """Use the production feedback database; clean up test-prefixed stories after each test."""
    client = MongoClient(MONGO_URL)
    db = client["feedback"]
    db.stories.delete_many({"_id": {"$regex": f"^{TEST_PREFIX}"}})
    yield db
    db.stories.delete_many({"_id": {"$regex": f"^{TEST_PREFIX}"}})
    client.close()


@pytest.fixture
def neo4j_driver():
    driver = GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean_neo4j(neo4j_driver):
    """Remove any nodes written by reconcile tests before and after each test."""
    def _cleanup(s):
        s.run(f"MATCH (s:Story) WHERE s.story_id STARTS WITH '{TEST_PREFIX}' DETACH DELETE s")
        s.run(f"MATCH (e:Entity) WHERE e.name STARTS WITH '{TEST_PREFIX}' DETACH DELETE e")

    with neo4j_driver.session() as s:
        _cleanup(s)
    yield
    with neo4j_driver.session() as s:
        _cleanup(s)


def _mongo_story(story_id: str, db) -> None:
    db.stories.insert_one({
        "_id": story_id,
        "story_text": "Test story.",
        "timestamp": datetime.now(UTC).replace(tzinfo=None),
    })


def _neo4j_story(story_id: str, driver) -> None:
    with driver.session() as s:
        s.run("MERGE (s:Story {story_id: $sid})", sid=story_id)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_reconcile_returns_correct_deleted_count(mongo_db, neo4j_driver):
    """reconcile() returns the actual number of nodes deleted, not 0."""
    live_id = "test-reconcile-count-live"
    orphan_id = "test-reconcile-count-orphan"

    _mongo_story(live_id, mongo_db)
    _neo4j_story(live_id, neo4j_driver)

    # Pre-clean any stale nodes left by other tests so the count is predictable.
    reconcile(mongo_db, neo4j_driver)

    # Now add exactly one orphan and verify the returned count matches.
    _neo4j_story(orphan_id, neo4j_driver)
    deleted, kept = reconcile(mongo_db, neo4j_driver)

    assert deleted == 1
    assert kept == 1


def test_reconcile_deletes_orphan_nodes(mongo_db, neo4j_driver):
    """Story nodes in Neo4j with no matching MongoDB document are deleted."""
    live_id = "test-reconcile-live"
    orphan_id = "test-reconcile-orphan"

    _mongo_story(live_id, mongo_db)
    _neo4j_story(live_id, neo4j_driver)
    _neo4j_story(orphan_id, neo4j_driver)

    reconcile(mongo_db, neo4j_driver)

    with neo4j_driver.session() as s:
        remaining = [r["sid"] for r in s.run(
            "MATCH (s:Story) WHERE s.story_id IN $ids RETURN s.story_id AS sid",
            ids=[live_id, orphan_id],
        )]
    assert live_id in remaining
    assert orphan_id not in remaining


def test_reconcile_dry_run_does_not_delete(mongo_db, neo4j_driver):
    """Dry-run reports what would be deleted but makes no changes."""
    live_id = "test-reconcile-live-dry"
    orphan_id = "test-reconcile-orphan-dry"

    _mongo_story(live_id, mongo_db)
    _neo4j_story(live_id, neo4j_driver)
    _neo4j_story(orphan_id, neo4j_driver)

    deleted, kept = reconcile(mongo_db, neo4j_driver, dry_run=True)

    assert deleted == 1
    assert kept == 1

    with neo4j_driver.session() as s:
        count = s.run(
            "MATCH (s:Story {story_id: $sid}) RETURN count(s) AS n",
            sid=orphan_id,
        ).single()["n"]
    assert count == 1  # still present


def test_reconcile_is_idempotent(mongo_db, neo4j_driver):
    """Running reconcile twice in a row yields 0 deletions on the second run."""
    live_id = "test-reconcile-idem"
    orphan_id = "test-reconcile-idem-orphan"

    _mongo_story(live_id, mongo_db)
    _neo4j_story(live_id, neo4j_driver)
    _neo4j_story(orphan_id, neo4j_driver)

    reconcile(mongo_db, neo4j_driver)
    deleted, kept = reconcile(mongo_db, neo4j_driver)

    assert deleted == 0
    assert kept == 1


def test_reconcile_detaches_relationships(mongo_db, neo4j_driver):
    """DETACH DELETE removes the Story node's relationships, leaving connected nodes intact."""
    orphan_id = "test-reconcile-rels"

    _neo4j_story(orphan_id, neo4j_driver)
    with neo4j_driver.session() as s:
        s.run(
            "MATCH (s:Story {story_id: $sid}) "
            "MERGE (e:Entity {name: 'test-reconcile-shared-entity'}) "
            "MERGE (s)-[:MENTIONS]->(e)",
            sid=orphan_id,
        )

    reconcile(mongo_db, neo4j_driver)

    with neo4j_driver.session() as s:
        story_count = s.run(
            "MATCH (s:Story {story_id: $sid}) RETURN count(s) AS n", sid=orphan_id
        ).single()["n"]
        entity_count = s.run(
            "MATCH (e:Entity {name: 'test-reconcile-shared-entity'}) RETURN count(e) AS n"
        ).single()["n"]

    assert story_count == 0  # orphan deleted
    assert entity_count == 1  # shared entity untouched
