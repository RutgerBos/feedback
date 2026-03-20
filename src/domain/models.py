"""
Domain models for SenseMaker feedback application.

These are pure domain objects with no infrastructure dependencies.
They use Pydantic for validation and immutability.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TriadCoordinates(BaseModel):
    """
    Responsibilities:
    - Hold barycentric coordinates for triad placement
    - Ensure coordinates are in valid range (0-1)

    Collaborators:
    - None (value object)

    Notes:
    - Immutable value object
    - Barycentric coordinates: x and y in range [0, 1]
    - Third coordinate z is implicit: z = 1 - x - y
    """

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)

    model_config = {"frozen": True}


class TriadPlacement(BaseModel):
    """
    Responsibilities:
    - Associate a triad ID with user's coordinate placement
    - Ensure placement references a valid triad

    Collaborators:
    - TriadCoordinates (value object)

    Notes:
    - Immutable value object
    - triad_id should match a configured triad
    """

    triad_id: str = Field(..., min_length=1)
    coordinates: TriadCoordinates

    model_config = {"frozen": True}


class StoryMetadata(BaseModel):
    """
    Responsibilities:
    - Hold optional contextual metadata about the story
    - Support pseudonymous identification

    Collaborators:
    - None (value object)

    Notes:
    - All fields are optional
    - No PII (personally identifiable information)
    - Immutable value object
    """

    user_pseudonym: str | None = None
    department: str | None = None
    role: str | None = None
    tool_context: str | None = None

    model_config = {"frozen": True}


class SentimentAnalysis(BaseModel):
    """
    Responsibilities:
    - Hold sentiment analysis results for a story
    - Capture emotion markers, process sentiment, and outcome sentiment

    Collaborators:
    - None (value object)

    Notes:
    - Immutable value object
    - Distinguishes between emotion about process vs outcome
    - emotion_markers: specific emotions detected (e.g. "frustration", "relief")
    - process_sentiment: overall sentiment about the process experienced
    - outcome_sentiment: overall sentiment about the outcome achieved
    """

    emotion_markers: list[str] = Field(default_factory=list)
    process_sentiment: str
    outcome_sentiment: str

    model_config = {"frozen": True}


class Story(BaseModel):
    """
    Responsibilities:
    - Hold complete story data (text, triads, metadata)
    - Validate story meets requirements (length, triad count)
    - Ensure story is always valid when constructed

    Collaborators:
    - TriadPlacement (value object)
    - StoryMetadata (value object)

    Notes:
    - Core domain aggregate root
    - Immutable after creation (except processing_status)
    - Story text: 50-2000 characters
    - Exactly 3 triad placements required
    """

    id: str = Field(..., min_length=1)
    story_text: str = Field(..., min_length=50, max_length=2000)
    triads: list[TriadPlacement] = Field(..., min_length=3, max_length=3)
    metadata: StoryMetadata | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processing_status: str = Field(default="pending")
    entities: list[dict[str, Any]] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    sentiment: SentimentAnalysis | None = None

    @field_validator("triads")
    @classmethod
    def validate_unique_triad_ids(cls, v: list[TriadPlacement]) -> list[TriadPlacement]:
        """Ensure triad IDs are unique within the story."""
        triad_ids = [placement.triad_id for placement in v]
        if len(triad_ids) != len(set(triad_ids)):
            raise ValueError("Triad IDs must be unique within a story")
        return v
