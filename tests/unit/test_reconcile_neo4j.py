"""Unit tests for scripts/reconcile_neo4j.py compute_orphans."""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.reconcile_neo4j import compute_orphans, reconcile


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


def test_reconcile_rejects_empty_scope_prefix():
    """An empty prefix must not accidentally turn a scoped run into a global run."""
    with pytest.raises(ValueError, match="must not be empty"):
        reconcile(None, None, story_id_prefix="")


def test_reconcile_without_prefix_queries_all_stories():
    """The production default remains an unscoped comparison of both stores."""
    mongo_db = MagicMock()
    mongo_db.stories.find.return_value = [{"_id": "story-1"}]
    session = MagicMock()
    session.run.return_value = [{"story_id": "story-1"}]
    neo4j_driver = MagicMock()
    neo4j_driver.session.return_value.__enter__.return_value = session

    deleted, kept = reconcile(mongo_db, neo4j_driver)

    assert (deleted, kept) == (0, 1)
    mongo_db.stories.find.assert_called_once_with({}, {"_id": 1})
    query = session.run.call_args.args[0]
    assert "WHERE" not in query
    assert session.run.call_args.kwargs == {}
