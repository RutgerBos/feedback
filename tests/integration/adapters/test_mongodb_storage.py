"""Integration tests for MongoDB storage adapter."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pymongo import MongoClient

from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.domain.models import (
    SentimentAnalysis,
    Story,
    StoryMetadata,
    TriadCoordinates,
    TriadPlacement,
)


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
        timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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
    from src.ports.errors import NotFoundError

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
        timestamp=datetime.now(UTC),
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


def test_count_stories_returns_zero_when_empty(storage_adapter):
    """count_stories returns 0 when no stories exist."""
    assert storage_adapter.count_stories() == 0


def test_count_stories_returns_correct_count(storage_adapter):
    """count_stories returns the number of saved stories."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]

    for _ in range(3):
        storage_adapter.save_story(Story(id=str(uuid4()), story_text=base_text, triads=triads))

    assert storage_adapter.count_stories() == 3


def test_list_stories_returns_empty_when_no_stories(storage_adapter):
    """list_stories returns empty list when no stories exist."""
    assert storage_adapter.list_stories() == []


def test_list_stories_returns_all_stories(storage_adapter):
    """list_stories returns all saved stories."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]

    for _ in range(3):
        storage_adapter.save_story(Story(id=str(uuid4()), story_text=base_text, triads=triads))

    stories = storage_adapter.list_stories()
    assert len(stories) == 3


def test_list_stories_ordered_newest_first(storage_adapter):
    """list_stories returns stories with newest first."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]
    older = Story(
        id=str(uuid4()), story_text=base_text, triads=triads,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
    )
    newer = Story(
        id=str(uuid4()), story_text=base_text, triads=triads,
        timestamp=datetime(2025, 6, 1, tzinfo=UTC),
    )
    storage_adapter.save_story(older)
    storage_adapter.save_story(newer)

    stories = storage_adapter.list_stories()
    assert stories[0].id == newer.id
    assert stories[1].id == older.id


def test_list_stories_respects_limit_and_offset(storage_adapter):
    """list_stories paginates correctly."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]

    for _ in range(5):
        storage_adapter.save_story(Story(id=str(uuid4()), story_text=base_text, triads=triads))

    page_one = storage_adapter.list_stories(limit=3, offset=0)
    page_two = storage_adapter.list_stories(limit=3, offset=3)

    assert len(page_one) == 3
    assert len(page_two) == 2


def test_update_story_entities_persists_and_round_trips(storage_adapter):
    """update_story_entities persists entities/themes and they survive a save/get cycle."""

    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )
    storage_adapter.save_story(story)

    entities = [{"name": "CI pipeline", "type": "tool"}, {"name": "deployment", "type": "process"}]
    themes = ["automation friction"]

    storage_adapter.update_story_entities(
        story_id=story.id,
        entities=entities,
        themes=themes,
        processing_status="processed",
    )

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.entities == entities
    assert retrieved.themes == themes
    assert retrieved.processing_status == "processed"


def test_update_story_entities_not_found_raises(storage_adapter):
    """update_story_entities raises NotFoundError for a missing story."""
    from src.ports.errors import NotFoundError

    with pytest.raises(NotFoundError):
        storage_adapter.update_story_entities(
            story_id="does-not-exist",
            entities=[],
            themes=[],
            processing_status="processed",
        )


def test_entities_survive_save_after_update(storage_adapter):
    """Extracted entities are not erased by a subsequent save_story call."""
    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )
    storage_adapter.save_story(story)

    entities = [{"name": "CI pipeline", "type": "tool"}]
    storage_adapter.update_story_entities(
        story_id=story.id, entities=entities, themes=[], processing_status="processed"
    )

    # Reload and re-save (simulates any system that re-saves a retrieved story)
    retrieved = storage_adapter.get_story(story.id)
    storage_adapter.save_story(retrieved)

    # Entities must survive the re-save
    after_resave = storage_adapter.get_story(story.id)
    assert after_resave.entities == entities
    assert after_resave.processing_status == "processed"


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


def test_update_story_sentiment_persists_and_round_trips(storage_adapter):
    """update_story_sentiment persists sentiment and it survives a save/get cycle."""

    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )
    storage_adapter.save_story(story)

    sentiment = SentimentAnalysis(
        emotion_markers=["frustration", "relief"],
        process_sentiment="negative",
        outcome_sentiment="positive",
    )

    storage_adapter.update_story_sentiment(
        story_id=story.id,
        sentiment=sentiment,
        processing_status="processed",
    )

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.sentiment is not None
    assert retrieved.sentiment.emotion_markers == ["frustration", "relief"]
    assert retrieved.sentiment.process_sentiment == "negative"
    assert retrieved.sentiment.outcome_sentiment == "positive"
    assert retrieved.processing_status == "processed"


def test_update_story_sentiment_none_round_trips(storage_adapter):
    """update_story_sentiment with None sentiment stores null and reads back as None."""

    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )
    storage_adapter.save_story(story)

    storage_adapter.update_story_sentiment(
        story_id=story.id,
        sentiment=None,
        processing_status="failed",
    )

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.sentiment is None
    assert retrieved.processing_status == "failed"


def test_update_story_sentiment_not_found_raises(storage_adapter):
    """update_story_sentiment raises NotFoundError for a missing story."""
    from src.ports.errors import NotFoundError

    with pytest.raises(NotFoundError):
        storage_adapter.update_story_sentiment(
            story_id="does-not-exist",
            sentiment=None,
            processing_status="failed",
        )
