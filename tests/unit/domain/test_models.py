"""Tests for domain models."""

from datetime import datetime

import pytest
from pydantic import ValidationError


def test_create_triad_coordinates():
    """Can create valid barycentric coordinates."""
    from src.domain.models import TriadCoordinates

    coords = TriadCoordinates(x=0.3, y=0.6)

    assert coords.x == 0.3
    assert coords.y == 0.6


def test_triad_coordinates_validates_range():
    """Coordinates must be in 0-1 range."""
    from src.domain.models import TriadCoordinates

    # Valid boundaries
    TriadCoordinates(x=0.0, y=0.0)
    TriadCoordinates(x=1.0, y=1.0)

    # Invalid - out of range
    with pytest.raises(ValidationError):
        TriadCoordinates(x=-0.1, y=0.5)

    with pytest.raises(ValidationError):
        TriadCoordinates(x=0.5, y=1.1)


def test_create_triad_placement():
    """Can create a triad placement with coordinates."""
    from src.domain.models import TriadCoordinates, TriadPlacement

    placement = TriadPlacement(
        triad_id="workflow_nature",
        coordinates=TriadCoordinates(x=0.4, y=0.5),
    )

    assert placement.triad_id == "workflow_nature"
    assert placement.coordinates.x == 0.4
    assert placement.coordinates.y == 0.5


def test_create_story_metadata():
    """Can create optional story metadata."""
    from src.domain.models import StoryMetadata

    metadata = StoryMetadata(
        user_pseudonym="user_123",
        department="engineering",
        role="developer",
        tool_context="CI/CD",
    )

    assert metadata.user_pseudonym == "user_123"
    assert metadata.department == "engineering"


def test_story_metadata_all_fields_optional():
    """All metadata fields are optional."""
    from src.domain.models import StoryMetadata

    metadata = StoryMetadata()
    assert metadata.user_pseudonym is None
    assert metadata.department is None


def test_create_story():
    """Can create a complete story."""
    from src.domain.models import Story, StoryMetadata, TriadCoordinates, TriadPlacement

    story = Story(
        id="test-uuid-123",
        story_text="I had to restart the CI pipeline three times today.",
        triads=[
            TriadPlacement(
                triad_id="workflow_nature",
                coordinates=TriadCoordinates(x=0.3, y=0.6),
            ),
            TriadPlacement(
                triad_id="understanding_quality",
                coordinates=TriadCoordinates(x=0.5, y=0.4),
            ),
            TriadPlacement(
                triad_id="value_character",
                coordinates=TriadCoordinates(x=0.2, y=0.7),
            ),
        ],
        metadata=StoryMetadata(department="engineering"),
        timestamp=datetime(2024, 11, 28, 12, 0, 0),
        processing_status="pending",
    )

    assert story.id == "test-uuid-123"
    assert len(story.triads) == 3
    assert story.processing_status == "pending"
    assert story.triads[0].triad_id == "workflow_nature"


def test_story_validates_minimum_text_length():
    """Story text must be at least 50 characters."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    # Valid - exactly 50 chars
    Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    # Invalid - too short
    with pytest.raises(ValidationError) as exc_info:
        Story(
            id="test-id",
            story_text="Too short",
            triads=[
                TriadPlacement(
                    triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
                TriadPlacement(
                    triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
                TriadPlacement(
                    triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
            ],
        )
    assert "story_text" in str(exc_info.value).lower()


def test_story_validates_maximum_text_length():
    """Story text must be at most 2000 characters."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    # Valid - exactly 2000 chars
    Story(
        id="test-id",
        story_text="a" * 2000,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    # Invalid - too long
    with pytest.raises(ValidationError) as exc_info:
        Story(
            id="test-id",
            story_text="a" * 2001,
            triads=[
                TriadPlacement(
                    triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
                TriadPlacement(
                    triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
                TriadPlacement(
                    triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
            ],
        )
    assert "story_text" in str(exc_info.value).lower()


def test_story_triads_count_is_not_constrained():
    """V2 stories accept any number of triads (0 to N); count constraint removed."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    # 0 triads — valid in V2 (participant used signification instead)
    Story(id="test-id", story_text="a" * 50, triads=[])

    # 2 triads — valid (e.g. only two signifiers configured)
    Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    # 4 triads — valid (e.g. four signifiers configured)
    Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t4", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )


# ── V2 domain model: ContextMetadata ──────────────────────────────────────────


def test_create_context_metadata():
    """Can create ContextMetadata with segmentation fields."""
    from src.domain.models import ContextMetadata

    ctx = ContextMetadata(department="engineering", role="developer", tool_context="CI/CD")

    assert ctx.department == "engineering"
    assert ctx.role == "developer"
    assert ctx.tool_context == "CI/CD"


def test_context_metadata_all_fields_optional():
    """All ContextMetadata fields are optional."""
    from src.domain.models import ContextMetadata

    ctx = ContextMetadata()

    assert ctx.department is None
    assert ctx.role is None
    assert ctx.tool_context is None


# ── V2 domain model: ParticipantMetadata ──────────────────────────────────────


def test_create_participant_metadata():
    """Can create ParticipantMetadata with pseudonym."""
    from src.domain.models import ParticipantMetadata

    pm = ParticipantMetadata(user_pseudonym="user_42")

    assert pm.user_pseudonym == "user_42"


def test_participant_metadata_all_fields_optional():
    """All ParticipantMetadata fields are optional."""
    from src.domain.models import ParticipantMetadata

    pm = ParticipantMetadata()

    assert pm.user_pseudonym is None


# ── V2 domain model: TriadResponseItem ────────────────────────────────────────


def test_create_triad_response_item():
    """Can create TriadResponseItem with valid signifier_id and coordinates."""
    from src.domain.models import TriadCoordinates, TriadResponseItem

    item = TriadResponseItem(
        kind="triad",
        signifier_id="workflow_nature",
        coordinates=TriadCoordinates(x=0.3, y=0.6),
    )

    assert item.kind == "triad"
    assert item.signifier_id == "workflow_nature"
    assert item.coordinates.x == 0.3
    assert item.coordinates.y == 0.6


def test_triad_response_item_rejects_out_of_range_coordinates():
    """TriadResponseItem rejects coordinates outside 0-1 range."""
    from src.domain.models import TriadCoordinates, TriadResponseItem

    with pytest.raises(ValidationError):
        TriadResponseItem(
            kind="triad",
            signifier_id="workflow_nature",
            coordinates=TriadCoordinates(x=1.5, y=0.5),
        )


# ── V2 domain model: StorySignification ───────────────────────────────────────


def test_create_story_signification():
    """Can create StorySignification with headline and responses."""
    from src.domain.models import StorySignification, TriadCoordinates, TriadResponseItem

    signification = StorySignification(
        headline="Pipeline kept breaking due to flaky tests",
        responses=[
            TriadResponseItem(
                kind="triad",
                signifier_id="workflow_nature",
                coordinates=TriadCoordinates(x=0.3, y=0.6),
            )
        ],
    )

    assert signification.headline == "Pipeline kept breaking due to flaky tests"
    assert len(signification.responses) == 1
    assert signification.responses[0].signifier_id == "workflow_nature"


def test_story_signification_headline_optional():
    """StorySignification headline is optional."""
    from src.domain.models import StorySignification, TriadCoordinates, TriadResponseItem

    signification = StorySignification(
        responses=[
            TriadResponseItem(
                kind="triad",
                signifier_id="workflow_nature",
                coordinates=TriadCoordinates(x=0.3, y=0.6),
            )
        ]
    )

    assert signification.headline is None


def test_story_signification_responses_can_be_empty():
    """StorySignification can have an empty responses list."""
    from src.domain.models import StorySignification

    signification = StorySignification()

    assert signification.responses == []
    assert signification.headline is None


# ── V2 Story: schema_version and relaxed triads constraint ────────────────────


def test_story_schema_version_defaults_to_2():
    """Story.schema_version defaults to 2 for new stories."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    story = Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    assert story.schema_version == 2


def test_story_can_be_created_without_triads():
    """V2 story can have an empty triads list (participant used signification)."""
    from src.domain.models import Story

    story = Story(
        id="test-id",
        story_text="a" * 50,
        triads=[],
    )

    assert story.triads == []


def test_story_can_hold_signification():
    """Story accepts a StorySignification object."""
    from src.domain.models import Story, StorySignification, TriadCoordinates, TriadResponseItem

    signification = StorySignification(
        headline="Broken pipeline day",
        responses=[
            TriadResponseItem(
                kind="triad",
                signifier_id="workflow_nature",
                coordinates=TriadCoordinates(x=0.3, y=0.6),
            )
        ],
    )

    story = Story(
        id="test-id",
        story_text="a" * 50,
        triads=[],
        signification=signification,
    )

    assert story.signification is not None
    assert story.signification.headline == "Broken pipeline day"


def test_story_signification_is_optional():
    """Story.signification defaults to None."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    story = Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    assert story.signification is None


def test_story_context_metadata_is_optional():
    """Story.context defaults to None."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    story = Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    assert story.context is None


def test_story_participant_metadata_is_optional():
    """Story.participant defaults to None."""
    from src.domain.models import Story, TriadCoordinates, TriadPlacement

    story = Story(
        id="test-id",
        story_text="a" * 50,
        triads=[
            TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="t3", coordinates=TriadCoordinates(x=0.5, y=0.5)),
        ],
    )

    assert story.participant is None
