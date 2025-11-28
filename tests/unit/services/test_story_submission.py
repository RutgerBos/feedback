"""Tests for story submission service."""

import pytest
from uuid import UUID
from src.services.story_submission import StorySubmissionService, StorySubmissionRequest
from src.domain.models import TriadPlacement, TriadCoordinates
from src.ports.storage import StoragePort
from src.domain.models import Story


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


def test_submit_story_requires_three_triads():
    """Story must have exactly 3 triad placements."""
    storage = FakeStorage()
    service = StorySubmissionService(storage)

    # Only 2 triads
    with pytest.raises(ValueError, match="triads"):
        request = StorySubmissionRequest(
            story_text="A" * 50,
            triads=[
                {"triad_id": "t1", "x": 0.3, "y": 0.6},
                {"triad_id": "t2", "x": 0.5, "y": 0.4},
            ],
        )
        service.submit_story(request)
