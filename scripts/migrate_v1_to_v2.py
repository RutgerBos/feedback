"""
Migrate V1 story documents to V2 format.

V1 format:
  - schema_version: absent or 1
  - triads: [{triad_id, coordinates: {x, y}}, ...]
  - metadata: {user_pseudonym, department, role, tool_context} | null

V2 format:
  - schema_version: 2
  - triads: []
  - signification: {headline: null, responses: [{kind: "triad", signifier_id, coordinates: {x, y}}, ...]}
  - context: {department, role, tool_context} | null
  - participant: {user_pseudonym} | null
  - metadata: null

This script is idempotent: documents already at schema_version=2 are skipped.
"""

import sys
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database


def transform_document(doc: dict[str, Any]) -> dict[str, Any]:
    """
    Return the MongoDB $set payload to migrate one V1 document to V2.

    Raises ValueError if the document is already V2 (schema_version == 2).
    """
    if doc.get("schema_version") == 2:
        raise ValueError(f"Document {doc.get('_id')} is already V2")

    # Build signification from triads
    responses = [
        {
            "kind": "triad",
            "signifier_id": t["triad_id"],
            "coordinates": {"x": t["coordinates"]["x"], "y": t["coordinates"]["y"]},
        }
        for t in doc.get("triads") or []
    ]
    signification = {"headline": None, "responses": responses}

    # Split metadata into context + participant
    meta = doc.get("metadata") or {}
    context = None
    if any(meta.get(k) is not None for k in ("department", "role", "tool_context")):
        context = {
            "department": meta.get("department"),
            "role": meta.get("role"),
            "tool_context": meta.get("tool_context"),
        }

    participant = None
    if meta.get("user_pseudonym") is not None:
        participant = {"user_pseudonym": meta["user_pseudonym"]}

    return {
        "schema_version": 2,
        "signification": signification,
        "context": context,
        "participant": participant,
        "triads": [],
        "metadata": None,
    }


def migrate(db: Database, *, dry_run: bool = False) -> tuple[int, int]:
    """
    Migrate all V1 documents in db.stories to V2.

    Returns (migrated_count, skipped_count).
    """
    migrated = 0
    skipped = 0

    cursor = db.stories.find(
        {"$or": [{"schema_version": {"$exists": False}}, {"schema_version": 1}]}
    )

    for doc in cursor:
        try:
            update = transform_document(doc)
        except ValueError:
            skipped += 1
            continue

        if not dry_run:
            db.stories.update_one({"_id": doc["_id"]}, {"$set": update})
        migrated += 1

    return migrated, skipped


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    mongo_uri = "mongodb://admin:password@localhost:27017/"

    client = MongoClient(mongo_uri)
    db = client["feedback"]

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating V1 → V2 stories in '{db.name}'...")
    migrated, skipped = migrate(db, dry_run=dry_run)
    print(f"Done. Migrated: {migrated}, Skipped (already V2): {skipped}")

    client.close()


if __name__ == "__main__":
    main()
