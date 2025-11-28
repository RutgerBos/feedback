"""Integration tests for stories API endpoint."""

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient


@pytest.fixture
def test_db():
    """Provide clean test database."""
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    db = client["test_feedback_api"]
    db.stories.delete_many({})
    yield db
    db.stories.delete_many({})
    client.close()


def test_submit_story_via_api(test_db):
    """Can submit a story via POST /api/stories."""
    from src.api.main import app

    # Override the storage dependency to use test database
    from src.api.stories import get_storage
    from src.adapters.mongodb_storage import MongoDBStorageAdapter

    def override_get_storage():
        return MongoDBStorageAdapter(test_db)

    app.dependency_overrides[get_storage] = override_get_storage

    client = TestClient(app)

    response = client.post(
        "/api/stories",
        json={
            "story_text": "I had to restart the CI pipeline three times today because of flaky tests. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                {"triad_id": "value_character", "x": 0.2, "y": 0.7},
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data
    assert data["message"] == "Story submitted successfully"

    # Verify story was saved to database
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert "CI pipeline" in story["story_text"]

    app.dependency_overrides.clear()


def test_submit_story_with_invalid_data(test_db):
    """Submitting invalid data returns 400."""
    from src.api.main import app
    from src.api.stories import get_storage
    from src.adapters.mongodb_storage import MongoDBStorageAdapter

    def override_get_storage():
        return MongoDBStorageAdapter(test_db)

    app.dependency_overrides[get_storage] = override_get_storage

    client = TestClient(app)

    # Too short story
    response = client.post(
        "/api/stories",
        json={
            "story_text": "Too short",
            "triads": [
                {"triad_id": "t1", "x": 0.3, "y": 0.6},
                {"triad_id": "t2", "x": 0.5, "y": 0.4},
                {"triad_id": "t3", "x": 0.2, "y": 0.7},
            ],
        },
    )

    assert response.status_code == 422  # Pydantic validation error

    app.dependency_overrides.clear()


def test_submit_story_with_metadata(test_db):
    """Can submit a story with optional metadata (department, role, user_pseudonym)."""
    from src.api.main import app
    from src.api.stories import get_storage
    from src.adapters.mongodb_storage import MongoDBStorageAdapter

    def override_get_storage():
        return MongoDBStorageAdapter(test_db)

    app.dependency_overrides[get_storage] = override_get_storage

    client = TestClient(app)

    response = client.post(
        "/api/stories",
        json={
            "story_text": "The deployment process has become much smoother after the recent automation improvements. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.8, "y": 0.1},
                {"triad_id": "understanding_quality", "x": 0.6, "y": 0.3},
                {"triad_id": "value_character", "x": 0.7, "y": 0.2},
            ],
            "metadata": {
                "department": "engineering",
                "role": "senior_developer",
                "user_pseudonym": "user_abc123"
            }
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data

    # Verify metadata was saved to database
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert story["metadata"]["department"] == "engineering"
    assert story["metadata"]["role"] == "senior_developer"
    assert story["metadata"]["user_pseudonym"] == "user_abc123"

    app.dependency_overrides.clear()


def test_submit_story_without_metadata(test_db):
    """Can submit a story without metadata - metadata is optional."""
    from src.api.main import app
    from src.api.stories import get_storage
    from src.adapters.mongodb_storage import MongoDBStorageAdapter

    def override_get_storage():
        return MongoDBStorageAdapter(test_db)

    app.dependency_overrides[get_storage] = override_get_storage

    client = TestClient(app)

    # Submit story without metadata field at all
    response = client.post(
        "/api/stories",
        json={
            "story_text": "The new feature made my workflow much faster and more efficient today. " * 2,
            "triads": [
                {"triad_id": "workflow_nature", "x": 0.9, "y": 0.05},
                {"triad_id": "understanding_quality", "x": 0.7, "y": 0.2},
                {"triad_id": "value_character", "x": 0.8, "y": 0.1},
            ],
            # No metadata field
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "story_id" in data

    # Verify story was saved without metadata
    story = test_db.stories.find_one({"_id": data["story_id"]})
    assert story is not None
    assert story.get("metadata") is None or story.get("metadata") == {}

    app.dependency_overrides.clear()
