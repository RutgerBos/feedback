"""Unit tests for scripts/reconcile_neo4j.py compute_orphans."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.reconcile_neo4j import compute_orphans


def test_compute_orphans_returns_ids_in_neo4j_not_in_mongo():
    mongo_ids = {"a", "b", "c"}
    neo4j_ids = {"a", "b", "c", "d", "e"}

    orphans = compute_orphans(mongo_ids, neo4j_ids)

    assert orphans == {"d", "e"}


def test_compute_orphans_returns_empty_when_all_ids_match():
    ids = {"a", "b", "c"}

    orphans = compute_orphans(ids, ids)

    assert orphans == set()


def test_compute_orphans_when_mongo_is_empty_all_neo4j_are_orphans():
    neo4j_ids = {"x", "y", "z"}

    orphans = compute_orphans(set(), neo4j_ids)

    assert orphans == neo4j_ids


def test_compute_orphans_when_neo4j_is_empty_returns_empty():
    mongo_ids = {"a", "b"}

    orphans = compute_orphans(mongo_ids, set())

    assert orphans == set()


def test_compute_orphans_ignores_ids_in_mongo_but_not_neo4j():
    """Stories in Mongo but missing from Neo4j are NOT orphans — that's a different problem."""
    mongo_ids = {"a", "b", "c"}
    neo4j_ids = {"a"}

    orphans = compute_orphans(mongo_ids, neo4j_ids)

    assert orphans == set()
