"""
Remove orphan Story nodes from Neo4j — stories present in Neo4j but absent from MongoDB.

Orphans accumulate when MongoDB is cleared directly (e.g. during development or testing)
without propagating deletions to Neo4j. This script computes the diff in Python and
sends only confirmed orphan IDs to Neo4j for deletion.

This script is idempotent: re-running it after a clean state deletes 0 nodes.
"""

import sys

from pymongo import MongoClient
from neo4j import GraphDatabase


def compute_orphans(mongo_ids: set[str], neo4j_ids: set[str]) -> set[str]:
    """Return story IDs present in Neo4j but absent from MongoDB."""
    return neo4j_ids - mongo_ids


def reconcile(mongo_db, neo4j_driver, *, dry_run: bool = False) -> tuple[int, int]:
    """
    Delete orphan Story nodes (and their relationships) from Neo4j.

    Returns (deleted_count, kept_count).
    """
    mongo_ids = {str(doc["_id"]) for doc in mongo_db.stories.find({}, {"_id": 1})}

    with neo4j_driver.session() as session:
        neo4j_ids = {
            row["story_id"]
            for row in session.run("MATCH (s:Story) RETURN s.story_id AS story_id")
            if row["story_id"] is not None
        }

    orphan_ids = compute_orphans(mongo_ids, neo4j_ids)
    kept = len(neo4j_ids) - len(orphan_ids)

    if orphan_ids and not dry_run:
        with neo4j_driver.session() as session:
            result = session.run(
                """
                UNWIND $story_ids AS story_id
                MATCH (s:Story {story_id: story_id})
                DETACH DELETE s
                RETURN count(s) AS deleted_count
                """,
                story_ids=list(orphan_ids),
            )
            deleted = result.single()["deleted_count"]
    else:
        deleted = len(orphan_ids)

    return deleted, kept


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    mongo_uri = "mongodb://admin:password@localhost:27017/"
    neo4j_uri = "bolt://localhost:7687"

    mongo_client = MongoClient(mongo_uri)
    neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", "password"))

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Reconciling Neo4j Story nodes against MongoDB...")

    deleted, kept = reconcile(mongo_client["feedback"], neo4j_driver, dry_run=dry_run)

    print(f"Done. {'Would delete' if dry_run else 'Deleted'}: {deleted}, Kept: {kept}")

    mongo_client.close()
    neo4j_driver.close()


if __name__ == "__main__":
    main()
