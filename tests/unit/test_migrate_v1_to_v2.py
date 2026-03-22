"""Unit tests for scripts/migrate_v1_to_v2.py transform_document."""

import sys
import os
import pytest

# scripts/ is not in the configured package path; add the project root so we can import it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.migrate_v1_to_v2 import transform_document


# ── Test 1: basic V1 triads become signification responses ────────────────────


def test_triads_become_signification_responses():
    doc = {
        "_id": "abc",
        "schema_version": 1,
        "triads": [
            {"triad_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
            {"triad_id": "understanding_quality", "coordinates": {"x": 0.1, "y": 0.9}},
        ],
        "metadata": None,
    }

    update = transform_document(doc)

    responses = update["signification"]["responses"]
    assert len(responses) == 2
    assert responses[0] == {
        "kind": "triad",
        "signifier_id": "workflow_nature",
        "coordinates": {"x": 0.3, "y": 0.6},
    }
    assert responses[1]["signifier_id"] == "understanding_quality"


# ── Test 2: schema_version becomes 2 ─────────────────────────────────────────


def test_schema_version_set_to_2():
    doc = {"_id": "x", "triads": [], "metadata": None}

    update = transform_document(doc)

    assert update["schema_version"] == 2


# ── Test 3: triads cleared ────────────────────────────────────────────────────


def test_triads_cleared_to_empty_list():
    doc = {
        "_id": "x",
        "triads": [{"triad_id": "t1", "coordinates": {"x": 0.5, "y": 0.5}}],
        "metadata": None,
    }

    update = transform_document(doc)

    assert update["triads"] == []


# ── Test 4: metadata department/role/tool_context → context ──────────────────


def test_metadata_splits_into_context():
    doc = {
        "_id": "x",
        "triads": [],
        "metadata": {
            "user_pseudonym": "alice",
            "department": "Engineering",
            "role": "Lead",
            "tool_context": "CI",
        },
    }

    update = transform_document(doc)

    assert update["context"] == {
        "department": "Engineering",
        "role": "Lead",
        "tool_context": "CI",
    }
    assert update["participant"] == {"user_pseudonym": "alice"}
    assert update["metadata"] is None


# ── Test 5: null metadata → null context and participant ──────────────────────


def test_null_metadata_yields_null_context_and_participant():
    doc = {"_id": "x", "triads": [], "metadata": None}

    update = transform_document(doc)

    assert update["context"] is None
    assert update["participant"] is None


# ── Test 6: missing metadata field → null context and participant ─────────────


def test_absent_metadata_field_yields_null_context_and_participant():
    doc = {"_id": "x", "triads": []}

    update = transform_document(doc)

    assert update["context"] is None
    assert update["participant"] is None


# ── Test 7: partial metadata (only pseudonym) → participant, no context ───────


def test_only_pseudonym_yields_participant_no_context():
    doc = {
        "_id": "x",
        "triads": [],
        "metadata": {"user_pseudonym": "bob", "department": None, "role": None, "tool_context": None},
    }

    update = transform_document(doc)

    assert update["participant"] == {"user_pseudonym": "bob"}
    assert update["context"] is None


# ── Test 8: already-V2 document raises ValueError ─────────────────────────────


def test_v2_document_raises_value_error():
    doc = {"_id": "x", "schema_version": 2, "triads": [], "metadata": None}

    with pytest.raises(ValueError):
        transform_document(doc)


# ── Test 9: empty triads list → empty signification responses ─────────────────


def test_empty_triads_yield_empty_responses():
    doc = {"_id": "x", "triads": [], "metadata": None}

    update = transform_document(doc)

    assert update["signification"]["responses"] == []
    assert update["signification"]["headline"] is None


# ── Test 10: missing schema_version treated as V1 ────────────────────────────


def test_missing_schema_version_treated_as_v1():
    doc = {
        "_id": "x",
        "triads": [{"triad_id": "t1", "coordinates": {"x": 0.2, "y": 0.8}}],
        "metadata": None,
    }

    update = transform_document(doc)

    assert update["schema_version"] == 2
    assert len(update["signification"]["responses"]) == 1
