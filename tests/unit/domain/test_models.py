"""Tests for domain models."""

import pytest
from datetime import datetime
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
    from src.domain.models import TriadPlacement, TriadCoordinates

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
    from src.domain.models import Story, TriadPlacement, TriadCoordinates, StoryMetadata

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
    from src.domain.models import Story, TriadPlacement, TriadCoordinates

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
    from src.domain.models import Story, TriadPlacement, TriadCoordinates

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


def test_story_requires_exactly_three_triads():
    """Story must have exactly 3 triad placements."""
    from src.domain.models import Story, TriadPlacement, TriadCoordinates

    # Invalid - only 2 triads
    with pytest.raises(ValidationError) as exc_info:
        Story(
            id="test-id",
            story_text="a" * 50,
            triads=[
                TriadPlacement(
                    triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
                TriadPlacement(
                    triad_id="t2", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
            ],
        )
    assert "triads" in str(exc_info.value).lower()

    # Invalid - 4 triads
    with pytest.raises(ValidationError) as exc_info:
        Story(
            id="test-id",
            story_text="a" * 50,
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
                TriadPlacement(
                    triad_id="t4", coordinates=TriadCoordinates(x=0.5, y=0.5)
                ),
            ],
        )
    assert "triads" in str(exc_info.value).lower()
