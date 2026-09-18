"""
Domain models for SenseMaker feedback application.

These are pure domain objects with no infrastructure dependencies.
They use Pydantic for validation and immutability.
"""

import math
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Canonical sentiment label for categorical aggregation.
SentimentLabel = Literal["positive", "negative", "neutral"]
_SENTIMENT_PREFIXES: tuple[str, ...] = ("positive", "negative", "neutral")


def _normalise_sentiment(value: str) -> str:
    """
    Normalise a raw LLM sentiment string to a canonical SentimentLabel.

    LLMs sometimes return values like "positive (embracing the new process)"
    or "Neutral with a hint of negativity". This function maps any value that
    starts with a known prefix to the canonical label, case-insensitively.

    Raises ValueError for values that do not start with a known prefix,
    so caller knows the model returned something genuinely unexpected.
    """
    lowered = value.strip().lower()
    for prefix in _SENTIMENT_PREFIXES:
        if lowered.startswith(prefix):
            return prefix
    raise ValueError(
        f"Unrecognised sentiment value {value!r}. "
        f"Expected a value starting with one of: {', '.join(_SENTIMENT_PREFIXES)}"
    )


class TriadCoordinates(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a valid position in triad signifier space
      - Measure distance to another triad position
    collaborators: []
    </crc>
    """

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)

    model_config = {"frozen": True}

    def distance_to(self, other: "TriadCoordinates") -> float:
        """Euclidean distance in 2D barycentric space."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


class TriadPlacement(BaseModel):
    """
    <crc>
    responsibilities:
      - Associate a triad signifier with a participant's position
    collaborators:
      - TriadCoordinates
    </crc>
    """

    triad_id: str = Field(..., min_length=1)
    coordinates: TriadCoordinates

    model_config = {"frozen": True}


_SQRT2 = math.sqrt(2)


class TriadProximity(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a unique proximity relationship between two stories
      - Express proximity distance as graph weight
    collaborators: []
    </crc>
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
    <crc>
    responsibilities:
      - Represent bounded story evidence for insight synthesis
    collaborators: []
    </crc>
    """

    story_id: str
    text_excerpt: str
    triad_positions: dict[str, dict[str, float]]

    model_config = {"frozen": True}


class SentimentSummary(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent aggregate process and outcome sentiment evidence
    collaborators: []
    </crc>
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
    <crc>
    responsibilities:
      - Provide bounded, structured evidence for insight synthesis
    collaborators:
      - StoryExcerpt
      - SentimentSummary
    </crc>
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
    <crc>
    responsibilities:
      - Represent a synthesized insight and its qualifications
    collaborators: []
    </crc>
    """

    narrative: str
    caveats: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class QueryIntent(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent an interpreted natural-language query for graph dispatch
    collaborators: []
    </crc>
    """

    operation: str
    entity: str | None = None
    theme: str | None = None
    explanation: str = ""

    model_config = {"frozen": True}


class StoryMetadata(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent legacy contextual and pseudonymous story metadata
    collaborators: []
    </crc>
    """

    user_pseudonym: str | None = None
    department: str | None = None
    role: str | None = None
    tool_context: str | None = None

    model_config = {"frozen": True}


class ContextMetadata(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent organisational context used to segment stories
    collaborators: []
    </crc>
    """

    department: str | None = None
    role: str | None = None
    tool_context: str | None = None

    model_config = {"frozen": True}


class ParticipantMetadata(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent pseudonymous participant identity separately from story context
    collaborators: []
    </crc>
    """

    user_pseudonym: str | None = None

    model_config = {"frozen": True}


class TriadResponseItem(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a participant's response to one triad signifier
    collaborators:
      - TriadCoordinates
    </crc>
    """

    kind: Literal["triad"] = "triad"
    signifier_id: str = Field(..., min_length=1)
    coordinates: TriadCoordinates

    model_config = {"frozen": True}


# Discriminated union for extensible signifier responses.
# Add DyadResponse, ChoiceResponse etc. here when new signifier types land.
SignifierResponse = TriadResponseItem


class StorySignification(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a participant's self-signification of a story
      - Preserve the participant's headline and signifier responses
    collaborators:
      - SignifierResponse
    </crc>
    """

    headline: str | None = None
    responses: list[SignifierResponse] = Field(default_factory=list)

    model_config = {"frozen": True}


class SentimentAnalysis(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent normalized process and outcome sentiment for a story
      - Preserve the emotional evidence supporting that sentiment
    collaborators: []
    </crc>
    """

    emotion_markers: list[str] = Field(default_factory=list)
    process_sentiment: SentimentLabel
    outcome_sentiment: SentimentLabel

    model_config = {"frozen": True}

    @field_validator("process_sentiment", "outcome_sentiment", mode="before")
    @classmethod
    def normalise_sentiment(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError(f"Expected a string, got {type(v).__name__}")
        return _normalise_sentiment(v)


class Story(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a valid participant story and its self-signification
      - Preserve enrichment and processing state across the story lifecycle
    collaborators:
      - TriadPlacement
      - StoryMetadata
      - StorySignification
      - ContextMetadata
      - ParticipantMetadata
    </crc>
    """

    id: str = Field(..., min_length=1)
    story_text: str = Field(..., min_length=50, max_length=2000)
    schema_version: int = Field(default=2)
    # V1 compat fields — present for existing stories read from MongoDB
    triads: list[TriadPlacement] = Field(default_factory=list)
    metadata: StoryMetadata | None = None
    # V2 fields
    signification: StorySignification | None = None
    context: ContextMetadata | None = None
    participant: ParticipantMetadata | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processing_status: str = Field(default="pending")
    processing_attempts: int = Field(default=0, ge=0)
    next_processing_at: datetime | None = None
    processing_error: str | None = None
    entity_status: str = Field(default="pending")
    sentiment_status: str = Field(default="pending")
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
