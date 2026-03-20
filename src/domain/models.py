"""
Domain models for SenseMaker feedback application.

These are pure domain objects with no infrastructure dependencies.
They use Pydantic for validation and immutability.
"""

import math
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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

    def distance_to(self, other: "TriadCoordinates") -> float:
        """Euclidean distance in 2D barycentric space."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


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


_SQRT2 = math.sqrt(2)


class TriadProximity(BaseModel):
    """
    Responsibilities:
    - Represent a proximity relationship between two stories in one triad's signifier space
    - Ensure canonical ordering of story IDs to prevent duplicate pairs
    - Compute weight from distance

    Collaborators:
    - None (value object)

    Notes:
    - Immutable value object
    - story_id_a is always lexicographically <= story_id_b (canonical ordering)
    - weight = 1 - distance / sqrt(2); ranges from 1.0 (identical) to ~0.0 (far apart)
    """

    story_id_a: str
    story_id_b: str
    triad_id: str
    distance: float

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def canonicalize_ids(cls, values: dict) -> dict:
        a = values.get("story_id_a", "")
        b = values.get("story_id_b", "")
        if a > b:
            values["story_id_a"], values["story_id_b"] = b, a
        return values

    @property
    def weight(self) -> float:
        """Proximity weight: 1.0 = identical position, 0.0 = maximum distance."""
        return 1.0 - self.distance / _SQRT2


class StoryExcerpt(BaseModel):
    """
    Responsibilities:
    - Hold a brief excerpt and triad positions for one story
    - Provide evidence context for LLM synthesis

    Collaborators:
    - None (value object)

    Notes:
    - Immutable value object
    - text_excerpt is capped at 300 characters
    - triad_positions: {triad_id: {x, y}} for spatial context
    """

    story_id: str
    text_excerpt: str
    triad_positions: dict[str, dict[str, float]]

    model_config = {"frozen": True}


class SentimentSummary(BaseModel):
    """
    Responsibilities:
    - Hold aggregated sentiment counts across a set of stories
    - Provide deterministic statistics for LLM synthesis context

    Collaborators:
    - None (value object)

    Notes:
    - Immutable value object
    - Counts are absolute (not percentages) so the LLM can reason about scale
    """

    positive_process: int = 0
    negative_process: int = 0
    neutral_process: int = 0
    positive_outcome: int = 0
    negative_outcome: int = 0
    neutral_outcome: int = 0

    model_config = {"frozen": True}


class InsightContext(BaseModel):
    """
    Responsibilities:
    - Bundle all structured context for an LLM synthesis call
    - Provide deterministic evidence: excerpts, theme counts, sentiment summary

    Collaborators:
    - StoryExcerpt (value object)
    - SentimentSummary (value object)

    Notes:
    - Immutable value object
    - theme_counts: {theme: count} computed before calling LLM
    - total_stories is the full match count (not just sampled_stories)
    - Capped at 20 story excerpts before reaching the LLM
    """

    query: str
    entity_name: str
    total_stories: int
    excerpts: list[StoryExcerpt]
    theme_counts: dict[str, int]
    sentiment_summary: SentimentSummary

    model_config = {"frozen": True}


class InsightOutput(BaseModel):
    """
    Responsibilities:
    - Hold structured LLM synthesis response

    Collaborators:
    - None (value object)

    Notes:
    - Immutable value object
    - caveats: known limitations or low-confidence observations from the LLM
    """

    narrative: str
    caveats: list[str] = Field(default_factory=list)

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
