"""Tests for story submission service."""

from uuid import UUID

import pytest

from src.domain.models import Story
from src.ports.storage import StoragePort
from src.services.story_submission import StorySubmissionRequest, StorySubmissionService

STORY_TEXT = "I had to restart the CI pipeline three times today. " * 5

V2_SIGNIFICATION = {
    "responses": [
        {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
        {"kind": "triad", "signifier_id": "understanding_quality", "coordinates": {"x": 0.5, "y": 0.4}},
        {"kind": "triad", "signifier_id": "value_character", "coordinates": {"x": 0.2, "y": 0.7}},
    ]
}


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

    result = service.submit_story(StorySubmissionRequest(
        story_text=STORY_TEXT,
        signification=V2_SIGNIFICATION,
    ))

    assert result.story_id is not None
    UUID(result.story_id)


def test_submit_story_saves_to_storage():
    """Submitting a story saves it via StoragePort."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="The deployment took two hours due to config issues. " * 3,
        signification=V2_SIGNIFICATION,
    ))

    assert storage.save_called
    assert result.story_id in storage.stories


def test_submit_story_with_context_and_participant():
    """Can submit a story with context and participant metadata."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="Database query optimization took most of the sprint. " * 3,
        signification=V2_SIGNIFICATION,
        context={"department": "engineering", "role": "developer", "tool_context": None},
        participant={"user_pseudonym": "user_abc"},
    ))

    saved = storage.stories[result.story_id]
    assert saved.context is not None
    assert saved.context.department == "engineering"
    assert saved.context.role == "developer"
    assert saved.participant is not None
    assert saved.participant.user_pseudonym == "user_abc"


def test_submit_story_sets_timestamp():
    """Submitted story has a timestamp set."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="Feature flag rollout was smooth and well-coordinated. " * 3,
        signification=V2_SIGNIFICATION,
    ))

    saved = storage.stories[result.story_id]
    assert saved.timestamp is not None


def test_submit_story_sets_pending_status():
    """Submitted story has processing_status set to 'pending'."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="Code review feedback helped improve the architecture. " * 3,
        signification=V2_SIGNIFICATION,
    ))

    saved = storage.stories[result.story_id]
    assert saved.processing_status == "pending"


def test_submit_story_validates_text_length():
    """Story text must meet length requirements."""
    with pytest.raises(ValueError, match="story_text"):
        StorySubmissionRequest(story_text="Too short")


def test_submit_story_rejects_v1_triads():
    """Non-empty triads field (V1 format) is rejected with a clear message."""
    with pytest.raises(ValueError, match="triads"):
        StorySubmissionRequest(
            story_text=STORY_TEXT,
            triads=[{"triad_id": "workflow_nature", "x": 0.3, "y": 0.6}],
        )


def test_submit_story_responses_count_not_constrained():
    """Signification can have any number of responses (0 to N)."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    # 0 responses — valid
    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        signification={"responses": []},
    ))
    assert result.story_id is not None

    # 2 responses — valid
    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        signification={"responses": [
            {"kind": "triad", "signifier_id": "t1", "coordinates": {"x": 0.3, "y": 0.6}},
            {"kind": "triad", "signifier_id": "t2", "coordinates": {"x": 0.5, "y": 0.4}},
        ]},
    ))
    assert result.story_id is not None


# ── Signifier ID validation against config ─────────────────────────────────────

VALID_TRIAD_IDS = {"workflow_nature", "understanding_quality", "value_character"}


def test_submit_story_accepts_known_signifier_ids():
    """Valid signifier_ids pass when a config allowlist is provided."""
    storage = FakeStorage()
    service = StorySubmissionService(storage, valid_triad_ids=VALID_TRIAD_IDS)

    result = service.submit_story(StorySubmissionRequest(
        story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
        signification=V2_SIGNIFICATION,
    ))
    assert result.story_id is not None


def test_submit_story_rejects_unknown_signifier_id():
    """Unknown signifier_id in signification.responses is rejected when allowlist is configured."""
    storage = FakeStorage()
    service = StorySubmissionService(storage, valid_triad_ids=VALID_TRIAD_IDS)

    with pytest.raises(ValueError, match="phantom_triad"):
        service.submit_story(StorySubmissionRequest(
            story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
            signification={"responses": [
                {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
                {"kind": "triad", "signifier_id": "phantom_triad", "coordinates": {"x": 0.5, "y": 0.4}},
            ]},
        ))


def test_submit_story_skips_signifier_id_validation_when_no_config():
    """Without an allowlist, any signifier_id is accepted."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)  # no valid_triad_ids

    result = service.submit_story(StorySubmissionRequest(
        story_text="The deployment pipeline failed twice before we caught the config issue. " * 2,
        signification={"responses": [
            {"kind": "triad", "signifier_id": "anything_goes", "coordinates": {"x": 0.3, "y": 0.6}},
        ]},
    ))
    assert result.story_id is not None


# ── V2 submission: signification, context, participant ─────────────────────────


def test_submit_story_with_signification():
    """V2 submission accepts signification and stores it on the story."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        signification={
            "headline": "Pipeline kept breaking",
            "responses": [
                {"kind": "triad", "signifier_id": "workflow_nature", "coordinates": {"x": 0.3, "y": 0.6}},
            ],
        },
    ))

    saved = storage.stories[result.story_id]
    assert saved.signification is not None
    assert saved.signification.headline == "Pipeline kept breaking"
    assert len(saved.signification.responses) == 1
    assert saved.signification.responses[0].signifier_id == "workflow_nature"


def test_submit_story_with_context_metadata():
    """V2 submission accepts context metadata and stores it."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        context={"department": "engineering", "role": "developer", "tool_context": "CI/CD"},
    ))

    saved = storage.stories[result.story_id]
    assert saved.context is not None
    assert saved.context.department == "engineering"
    assert saved.context.role == "developer"
    assert saved.context.tool_context == "CI/CD"


def test_submit_story_with_participant_metadata():
    """V2 submission accepts participant metadata and stores it."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(
        story_text="A" * 50,
        participant={"user_pseudonym": "user_42"},
    ))

    saved = storage.stories[result.story_id]
    assert saved.participant is not None
    assert saved.participant.user_pseudonym == "user_42"


def test_submit_story_schema_version_is_2():
    """V2 submission sets schema_version=2 on the stored story."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    result = service.submit_story(StorySubmissionRequest(story_text="A" * 50))

    saved = storage.stories[result.story_id]
    assert saved.schema_version == 2
