"""Integration tests for MongoDB storage adapter."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pymongo import MongoClient
from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.domain.models import Story, TriadPlacement, TriadCoordinates, StoryMetadata


@pytest.fixture
def mongo_client():
    """Create a MongoDB client for testing."""
    # Use a test database
    client = MongoClient("mongodb://admin:password@localhost:27017/")
    yield client
    # Cleanup
    client.drop_database("test_feedback")
    client.close()


@pytest.fixture
def clean_db(mongo_client):
    """Provide a clean test database."""
    db = mongo_client["test_feedback"]
    # Clear any existing data
    db.stories.delete_many({})
    yield db
    # Cleanup after test
    db.stories.delete_many({})


@pytest.fixture
def storage_adapter(clean_db):
    """Create a MongoDB storage adapter for testing."""
    return MongoDBStorageAdapter(clean_db)


def test_save_story_returns_id(storage_adapter):
    """Saving a story returns its ID."""
    story = Story(
        id=str(uuid4()),
        story_text="I had to restart the CI pipeline three times today. " * 5,  # Make it long enough
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        metadata=StoryMetadata(department="engineering"),
        timestamp=datetime.now(timezone.utc),
    )

    story_id = storage_adapter.save_story(story)

    assert story_id == story.id
    assert isinstance(story_id, str)


def test_saved_story_can_be_retrieved(storage_adapter):
    """Story can be retrieved after being saved."""
    original_story = Story(
        id=str(uuid4()),
        story_text="The deployment process took two hours because of configuration issues. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        metadata=StoryMetadata(department="engineering", role="developer"),
        timestamp=datetime.now(timezone.utc),
    )

    story_id = storage_adapter.save_story(original_story)
    retrieved_story = storage_adapter.get_story(story_id)

    assert retrieved_story.id == original_story.id
    assert retrieved_story.story_text == original_story.story_text
    assert len(retrieved_story.triads) == 3
    assert retrieved_story.triads[0].triad_id == "workflow_nature"
    assert retrieved_story.triads[0].coordinates.x == 0.3
    assert retrieved_story.metadata.department == "engineering"
    assert retrieved_story.metadata.role == "developer"


def test_get_nonexistent_story_raises_error(storage_adapter):
    """Attempting to get a story that doesn't exist raises an error."""
    from src.adapters.mongodb_storage import NotFoundError

    with pytest.raises(NotFoundError, match="Story not found"):
        storage_adapter.get_story("nonexistent-id-12345")


def test_story_stored_with_correct_structure(storage_adapter, clean_db):
    """Story is stored in MongoDB with correct document structure."""
    story = Story(
        id=str(uuid4()),
        story_text="Testing the MongoDB storage with a sufficiently long story. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        timestamp=datetime.now(timezone.utc),
    )

    storage_adapter.save_story(story)

    # Check the raw MongoDB document
    doc = clean_db.stories.find_one({"_id": story.id})
    assert doc is not None
    assert doc["story_text"] == story.story_text
    assert len(doc["triads"]) == 3
    assert doc["triads"][0]["triad_id"] == "workflow_nature"
    assert doc["triads"][0]["coordinates"]["x"] == 0.3
    assert doc["processing_status"] == "pending"
    assert "timestamp" in doc


def test_save_multiple_stories(storage_adapter):
    """Can save multiple stories."""
    story1 = Story(
        id=str(uuid4()),
        story_text="First story about CI/CD pipeline issues and troubleshooting. " * 2,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )

    story2 = Story(
        id=str(uuid4()),
        story_text="Second story about database performance optimization efforts. " * 2,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.4, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.6, y=0.3)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.1, y=0.8)),
        ],
    )

    id1 = storage_adapter.save_story(story1)
    id2 = storage_adapter.save_story(story2)

    assert id1 != id2

    retrieved1 = storage_adapter.get_story(id1)
    retrieved2 = storage_adapter.get_story(id2)

    assert retrieved1.story_text != retrieved2.story_text
