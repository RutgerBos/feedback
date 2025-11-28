"""
Domain models for SenseMaker feedback application.

These are pure domain objects with no infrastructure dependencies.
They use Pydantic for validation and immutability.
"""

from datetime import datetime, timezone
from typing import List, Optional
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

    user_pseudonym: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    tool_context: Optional[str] = None

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
    triads: List[TriadPlacement] = Field(..., min_length=3, max_length=3)
    metadata: Optional[StoryMetadata] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_status: str = Field(default="pending")

    @field_validator("triads")
    @classmethod
    def validate_unique_triad_ids(cls, v: List[TriadPlacement]) -> List[TriadPlacement]:
        """Ensure triad IDs are unique within the story."""
        triad_ids = [placement.triad_id for placement in v]
        if len(triad_ids) != len(set(triad_ids)):
            raise ValueError("Triad IDs must be unique within a story")
        return v
