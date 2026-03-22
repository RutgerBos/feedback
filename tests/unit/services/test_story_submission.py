"""Tests for story submission service."""

from uuid import UUID

import pytest

from src.domain.models import Story
from src.ports.storage import StoragePort
from src.services.story_submission import StorySubmissionRequest, StorySubmissionService


class FakeStorage(StoragePort):
    """Fake storage for testing - no mocks!"""

    def __init__(self):
        self.stories = {}
        self.save_called = False

    def save_story(self, story: Story) -> str:
        self.save_called = True
        self.stories[story.id] = story
        return story.id

    def get_story(self, story_id: str) -> Story:
        return self.stories[story_id]

    def count_stories(self, from_date=None, to_date=None) -> int:
        return len(self.stories)

    def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list[Story]:
        return list(self.stories.values())[offset:offset + limit]

    def update_story_entities(self, story_id: str, entities: list, themes: list, entity_status: str) -> None:
        pass

    def update_story_sentiment(self, story_id: str, sentiment, sentiment_status: str) -> None:
        pass


def test_submit_story_generates_uuid():
    """Submitting a story generates a UUID for it."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="I had to restart the CI pipeline three times today. " * 5,
        triads=[
            {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
            {"triad_id": "value_character", "x": 0.2, "y": 0.7},
        ],
    )

    result = service.submit_story(request)

    assert result.story_id is not None
    # Verify it's a valid UUID
    UUID(result.story_id)


def test_submit_story_saves_to_storage():
    """Submitting a story saves it via StoragePort."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="The deployment took two hours due to config issues. " * 3,
        triads=[
            {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
            {"triad_id": "value_character", "x": 0.2, "y": 0.7},
        ],
    )

    result = service.submit_story(request)

    assert storage.save_called
    assert result.story_id in storage.stories


def test_submit_story_with_metadata():
    """Can submit a story with optional metadata."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="Database query optimization took most of the sprint. " * 3,
        triads=[
            {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
            {"triad_id": "value_character", "x": 0.2, "y": 0.7},
        ],
        metadata={"department": "engineering", "role": "developer"},
    )

    result = service.submit_story(request)

    saved_story = storage.stories[result.story_id]
    assert saved_story.metadata is not None
    assert saved_story.metadata.department == "engineering"
    assert saved_story.metadata.role == "developer"


def test_submit_story_sets_timestamp():
    """Submitted story has a timestamp set."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="Feature flag rollout was smooth and well-coordinated. " * 3,
        triads=[
            {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
            {"triad_id": "value_character", "x": 0.2, "y": 0.7},
        ],
    )

    result = service.submit_story(request)

    saved_story = storage.stories[result.story_id]
    assert saved_story.timestamp is not None


def test_submit_story_sets_pending_status():
    """Submitted story has processing_status set to 'pending'."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="Code review feedback helped improve the architecture. " * 3,
        triads=[
            {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
            {"triad_id": "value_character", "x": 0.2, "y": 0.7},
        ],
    )

    result = service.submit_story(request)

    saved_story = storage.stories[result.story_id]
    assert saved_story.processing_status == "pending"


def test_submit_story_validates_text_length():
    """Story text must meet length requirements."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    # Too short
    with pytest.raises(ValueError, match="story_text"):
        request = StorySubmissionRequest(
            story_text="Too short",
            triads=[
                {"triad_id": "t1", "x": 0.3, "y": 0.6},
                {"triad_id": "t2", "x": 0.5, "y": 0.4},
                {"triad_id": "t3", "x": 0.2, "y": 0.7},
            ],
        )
        service.submit_story(request)


def test_submit_story_triads_count_not_constrained():
    """V2 stories accept any number of triads (0 to N)."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    # 0 triads — valid in V2
    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        triads=[],
    ))
    assert result.story_id is not None

    # 2 triads — valid
    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        triads=[
            {"triad_id": "t1", "x": 0.3, "y": 0.6},
            {"triad_id": "t2", "x": 0.5, "y": 0.4},
        ],
    ))
    assert result.story_id is not None


# ── Triad ID validation against config ────────────────────────────────────────

VALID_TRIAD_IDS = {"workflow_nature", "understanding_quality", "value_character"}


def test_submit_story_accepts_known_triad_ids():
    """Valid triad_ids pass when a config allowlist is provided."""
    storage = FakeStorage()
    service = StorySubmissionService(storage, valid_triad_ids=VALID_TRIAD_IDS)

    request = StorySubmissionRequest(
        story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
        triads=[
            {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
            {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
            {"triad_id": "value_character", "x": 0.2, "y": 0.7},
        ],
    )

    result = service.submit_story(request)
    assert result.story_id is not None


def test_submit_story_rejects_unknown_triad_id():
    """Unknown triad_id is rejected with ValueError when allowlist is configured."""
    storage = FakeStorage()
    service = StorySubmissionService(storage, valid_triad_ids=VALID_TRIAD_IDS)

    with pytest.raises(ValueError, match="phantom_triad"):
        service.submit_story(StorySubmissionRequest(
            story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
            triads=[
                {"triad_id": "workflow_nature", "x": 0.3, "y": 0.6},
                {"triad_id": "understanding_quality", "x": 0.5, "y": 0.4},
                {"triad_id": "phantom_triad", "x": 0.2, "y": 0.7},
            ],
        ))


def test_submit_story_rejects_unknown_signifier_id_in_signification():
    """Unknown signifier_id in signification.responses is rejected when allowlist is configured."""
    storage = FakeStorage()
    service = StorySubmissionService(storage, valid_triad_ids=VALID_TRIAD_IDS)

    with pytest.raises(ValueError, match="phantom_signifier"):
        service.submit_story(StorySubmissionRequest(
            story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
            triads=[],
            signification={
                "responses": [
                    {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                    {"kind": "triad", "signifier_id": "phantom_signifier", "coordinates": {"x": 0.5, "y": 0.4}},
                ]
            },
        ))


def test_submit_story_skips_triad_id_validation_when_no_config():
    """Without an allowlist, any triad_id is accepted (backward-compatible)."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)  # no valid_triad_ids

    result = service.submit_story(StorySubmissionRequest(
        story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
        triads=[
            {"triad_id": "anything_goes", "x": 0.3, "y": 0.6},
            {"triad_id": "whatever", "x": 0.5, "y": 0.4},
            {"triad_id": "unchecked", "x": 0.2, "y": 0.7},
        ],
    ))

    assert result.story_id is not None


# ── V2 submission: signification, context, participant ────────────────────────


def test_submit_story_with_signification():
    """V2 submission accepts signification and stores it on the story."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="A" * 50,
        triads=[],
        signification={
            "headline": "Pipeline kept breaking",
            "responses": [
                {
                    "kind": "triad",
                    "signifier_id": "workflow_nature",
                    "coordinates": {"x": 0.3, "y": 0.6},
                }
            ],
        },
    )

    result = service.submit_story(request)

    saved = storage.stories[result.story_id]
    assert saved.signification is not None
    assert saved.signification.headline == "Pipeline kept breaking"
    assert len(saved.signification.responses) == 1
    assert saved.signification.responses[0].signifier_id == "workflow_nature"


def test_submit_story_with_context_metadata():
    """V2 submission accepts context metadata and stores it."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="A" * 50,
        triads=[],
        context={"department": "engineering", "role": "developer", "tool_context": "CI/CD"},
    )

    result = service.submit_story(request)

    saved = storage.stories[result.story_id]
    assert saved.context is not None
    assert saved.context.department == "engineering"
    assert saved.context.role == "developer"
    assert saved.context.tool_context == "CI/CD"


def test_submit_story_with_participant_metadata():
    """V2 submission accepts participant metadata and stores it."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    request = StorySubmissionRequest(
        story_text="A" * 50,
        triads=[],
        participant={"user_pseudonym": "user_42"},
    )

    result = service.submit_story(request)

    saved = storage.stories[result.story_id]
    assert saved.participant is not None
    assert saved.participant.user_pseudonym == "user_42"


def test_submit_story_schema_version_is_2():
    """V2 submission sets schema_version=2 on the stored story."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        triads=[],
    ))

    saved = storage.stories[result.story_id]
    assert saved.schema_version == 2
