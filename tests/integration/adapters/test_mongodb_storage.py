"""Integration tests for MongoDB storage adapter."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pymongo import MongoClient

from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.domain.models import (
    ContextMetadata,
    ParticipantMetadata,
    SentimentAnalysis,
    Story,
    StoryMetadata,
    StorySignification,
    TriadCoordinates,
    TriadPlacement,
    TriadResponseItem,
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


def test_list_stories_filters_by_from_date(storage_adapter):
    """list_stories excludes stories before from_date."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]
    old = Story(id=str(uuid4()), story_text=base_text, triads=triads,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    new = Story(id=str(uuid4()), story_text=base_text, triads=triads,
                timestamp=datetime(2026, 3, 15, tzinfo=UTC))
    storage_adapter.save_story(old)
    storage_adapter.save_story(new)

    results = storage_adapter.list_stories(from_date=datetime(2026, 3, 1))
    ids = [s.id for s in results]
    assert new.id in ids
    assert old.id not in ids


def test_list_stories_filters_by_to_date(storage_adapter):
    """list_stories excludes stories after to_date."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]
    old = Story(id=str(uuid4()), story_text=base_text, triads=triads,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC))
    new = Story(id=str(uuid4()), story_text=base_text, triads=triads,
                timestamp=datetime(2026, 3, 15, tzinfo=UTC))
    storage_adapter.save_story(old)
    storage_adapter.save_story(new)

    results = storage_adapter.list_stories(to_date=datetime(2026, 2, 1))
    ids = [s.id for s in results]
    assert old.id in ids
    assert new.id not in ids


def test_count_stories_filters_by_date_range(storage_adapter):
    """count_stories respects from_date and to_date."""
    base_text = "A story long enough to pass validation. " * 3
    triads = [
        TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.3, y=0.6)),
        TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.4)),
        TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.2, y=0.7)),
    ]
    for ts in [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC),
               datetime(2026, 3, 15, tzinfo=UTC)]:
        storage_adapter.save_story(Story(id=str(uuid4()), story_text=base_text,
                                         triads=triads, timestamp=ts))

    assert storage_adapter.count_stories() == 3
    assert storage_adapter.count_stories(from_date=datetime(2026, 2, 1)) == 2
    assert storage_adapter.count_stories(to_date=datetime(2026, 1, 31)) == 1
    assert storage_adapter.count_stories(
        from_date=datetime(2026, 2, 1), to_date=datetime(2026, 2, 28)
    ) == 1


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
        entity_status="processed",
    )

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.entities == entities
    assert retrieved.themes == themes
    assert retrieved.entity_status == "processed"


def test_update_story_entities_not_found_raises(storage_adapter):
    """update_story_entities raises NotFoundError for a missing story."""
    from src.ports.errors import NotFoundError

    with pytest.raises(NotFoundError):
        storage_adapter.update_story_entities(
            story_id="does-not-exist",
            entities=[],
            themes=[],
            entity_status="processed",
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
        story_id=story.id, entities=entities, themes=[], entity_status="processed"
    )

    # Reload and re-save (simulates any system that re-saves a retrieved story)
    retrieved = storage_adapter.get_story(story.id)
    storage_adapter.save_story(retrieved)

    # Entities must survive the re-save
    after_resave = storage_adapter.get_story(story.id)
    assert after_resave.entities == entities
    assert after_resave.entity_status == "processed"


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
        sentiment_status="processed",
    )

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.sentiment is not None
    assert retrieved.sentiment.emotion_markers == ["frustration", "relief"]
    assert retrieved.sentiment.process_sentiment == "negative"
    assert retrieved.sentiment.outcome_sentiment == "positive"
    assert retrieved.sentiment_status == "processed"


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
        sentiment_status="failed",
    )

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.sentiment is None
    assert retrieved.sentiment_status == "failed"


def test_update_story_sentiment_not_found_raises(storage_adapter):
    """update_story_sentiment raises NotFoundError for a missing story."""
    from src.ports.errors import NotFoundError

    with pytest.raises(NotFoundError):
        storage_adapter.update_story_sentiment(
            story_id="does-not-exist",
            sentiment=None,
            sentiment_status="failed",
        )


def test_legacy_free_form_sentiment_degrades_gracefully_on_read(storage_adapter, clean_db):
    """Docs with pre-constraint free-form sentiment values read back with sentiment=None."""
    from uuid import uuid4 as _uuid4
    story_id = str(_uuid4())
    from datetime import UTC, datetime
    clean_db.stories.insert_one({
        "_id": story_id,
        "story_text": "The CI pipeline was an absolute mess for the entire week, blocking everyone.",
        "triads": [],
        "signification": {"headline": None, "responses": []},
        "schema_version": 2,
        "processing_status": "pending",
        "sentiment_status": "processed",
        "timestamp": datetime.now(UTC),
        # Legacy free-form value that would have been stored before the constraint
        "sentiment": {
            "emotion_markers": ["frustration"],
            "process_sentiment": "cautious",
            "outcome_sentiment": "neutral with a hint of negativity",
        },
    })

    retrieved = storage_adapter.get_story(story_id)
    # "cautious" is unrecognisable → degraded to None
    # "neutral with a hint of negativity" would normalise, but "cautious" fails first
    assert retrieved.sentiment is None


# ── V2 field round-trips ───────────────────────────────────────────────────────


def test_v2_story_with_signification_round_trips(storage_adapter):
    """V2 story with StorySignification saves and retrieves correctly."""
    signification = StorySignification(
        headline="Pipeline kept breaking due to flaky tests",
        responses=[
            TriadResponseItem(
                kind="triad",
                signifier_id="workflow_nature",
                coordinates=TriadCoordinates(x=0.3, y=0.6),
            ),
        ],
    )
    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[],
        signification=signification,
        schema_version=2,
    )
    storage_adapter.save_story(story)

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.schema_version == 2
    assert retrieved.signification is not None
    assert retrieved.signification.headline == "Pipeline kept breaking due to flaky tests"
    assert len(retrieved.signification.responses) == 1
    assert retrieved.signification.responses[0].signifier_id == "workflow_nature"
    assert retrieved.signification.responses[0].coordinates.x == 0.3


def test_v2_story_with_context_and_participant_round_trips(storage_adapter):
    """V2 story with ContextMetadata and ParticipantMetadata saves and retrieves."""
    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[],
        context=ContextMetadata(department="engineering", role="developer", tool_context="CI/CD"),
        participant=ParticipantMetadata(user_pseudonym="user_42"),
        schema_version=2,
    )
    storage_adapter.save_story(story)

    retrieved = storage_adapter.get_story(story.id)
    assert retrieved.context is not None
    assert retrieved.context.department == "engineering"
    assert retrieved.context.role == "developer"
    assert retrieved.context.tool_context == "CI/CD"
    assert retrieved.participant is not None
    assert retrieved.participant.user_pseudonym == "user_42"


def test_v2_story_schema_version_persists(storage_adapter):
    """schema_version is written to MongoDB and read back."""
    story = Story(
        id=str(uuid4()),
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[],
        schema_version=2,
    )
    storage_adapter.save_story(story)

    raw = storage_adapter.collection.find_one({"_id": story.id})
    assert raw["schema_version"] == 2


def test_find_story_ids_requiring_processing_returns_pending_stories(storage_adapter):
    """Stories with entity_status or sentiment_status != 'processed' are returned."""
    processed_story = Story(
        id=str(uuid4()),
        story_text="This story has been fully processed already by the system.",
        timestamp=datetime.now(UTC).replace(tzinfo=None),
    )
    storage_adapter.save_story(processed_story)
    storage_adapter.update_story_entities(processed_story.id, [], [], "processed")
    storage_adapter.update_story_sentiment(processed_story.id, None, "processed")

    pending_story = Story(
        id=str(uuid4()),
        story_text="This story is still pending full processing by the worker.",
        timestamp=datetime.now(UTC).replace(tzinfo=None),
    )
    storage_adapter.save_story(pending_story)

    result = storage_adapter.find_story_ids_requiring_processing()

    assert pending_story.id in result
    assert processed_story.id not in result


def test_find_story_ids_requiring_processing_includes_partially_processed(storage_adapter):
    """A story with entity done but sentiment pending is still returned."""
    story = Story(
        id=str(uuid4()),
        story_text="Entity extracted but sentiment not yet done for this test.",
        timestamp=datetime.now(UTC).replace(tzinfo=None),
    )
    storage_adapter.save_story(story)
    storage_adapter.update_story_entities(story.id, [], [], "processed")

    result = storage_adapter.find_story_ids_requiring_processing()

    assert story.id in result


def test_find_story_ids_requiring_processing_empty_when_all_processed(storage_adapter):
    """Returns empty list when all stories are fully processed."""
    story = Story(
        id=str(uuid4()),
        story_text="Fully processed story for empty result test verification.",
        timestamp=datetime.now(UTC).replace(tzinfo=None),
    )
    storage_adapter.save_story(story)
    storage_adapter.update_story_entities(story.id, [], [], "processed")
    storage_adapter.update_story_sentiment(story.id, None, "processed")

    result = storage_adapter.find_story_ids_requiring_processing()

    assert result == []


def test_v1_document_reads_back_without_v2_fields(storage_adapter):
    """A V1 document (no schema_version/signification/context/participant) reads safely."""
    story_id = str(uuid4())
    # Insert raw V1-style document directly into MongoDB
    storage_adapter.collection.insert_one({
        "_id": story_id,
        "story_text": "CI failures blocked our deployment repeatedly this sprint. " * 3,
        "triads": [
            {"triad_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
            {"triad_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
            {"triad_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
        ],
        "metadata": {"department": "engineering", "role": "dev", "tool_context": None, "user_pseudonym": None},
        "timestamp": datetime.now(UTC),
        "processing_status": "pending",
        "entity_status": "pending",
        "sentiment_status": "pending",
        "entities": [],
        "themes": [],
        "sentiment": None,
    })

    retrieved = storage_adapter.get_story(story_id)
    # V1 docs have no schema_version stored — adapter should default to 1
    assert retrieved.schema_version == 1
    assert retrieved.signification is None
    assert retrieved.context is None
    assert retrieved.participant is None
    assert len(retrieved.triads) == 3
