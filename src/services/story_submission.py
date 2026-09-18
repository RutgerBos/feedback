"""
Story submission service.

Coordinates the submission of new stories, including validation,
ID generation, and persistence.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.geometry import is_point_in_triad_triangle
from src.domain.models import (
    ContextMetadata,
    ParticipantMetadata,
    Story,
    StorySignification,
    TriadCoordinates,
    TriadResponseItem,
)
from src.ports.storage import StoragePort


class CoordinatesRequest(BaseModel):
    """x/y coordinates in [0, 1]."""

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def must_lie_in_triad_triangle(self) -> "CoordinatesRequest":
        """Match the normalized triangle used by the submission UI."""
        if not is_point_in_triad_triangle(self.x, self.y):
            raise ValueError("coordinates must lie inside the triad triangle")
        return self


class TriadResponseRequest(BaseModel):
    """One response placement in a signification."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["triad"] = "triad"
    signifier_id: str = Field(..., min_length=1)
    coordinates: CoordinatesRequest


class SignificationRequest(BaseModel):
    """V2 signification block sent by the client."""

    model_config = ConfigDict(extra="forbid")

    headline: str | None = None
    responses: list[TriadResponseRequest] = Field(default_factory=list)

    @field_validator("responses")
    @classmethod
    def reject_duplicate_signifier_ids(
        cls, v: list[TriadResponseRequest]
    ) -> list[TriadResponseRequest]:
        """Reject duplicate signifier_id entries."""
        ids = [r.signifier_id for r in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate signifier_id values are not allowed in responses.")
        return v


class ContextRequest(BaseModel):
    """Typed context metadata sent by the client."""

    model_config = ConfigDict(extra="forbid")

    department: str | None = None
    role: str | None = None
    tool_context: str | None = None


class ParticipantRequest(BaseModel):
    """Typed participant metadata sent by the client."""

    model_config = ConfigDict(extra="forbid")

    user_pseudonym: str | None = None


class StorySubmissionRequest(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent a valid story-submission request
    collaborators:
      - SignificationRequest
      - ContextRequest
      - ParticipantRequest
    </crc>
    """

    story_text: str = Field(..., min_length=50, max_length=2000)
    triads: list[dict[str, Any]] = Field(default_factory=list)
    signification: SignificationRequest
    context: ContextRequest | None = None
    participant: ParticipantRequest | None = None

    @field_validator("triads")
    @classmethod
    def reject_v1_triads(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reject legacy V1 triads payload with a helpful error."""
        if v:
            raise ValueError(
                "The 'triads' field is no longer accepted. "
                "Submit coordinates via 'signification.responses' instead."
            )
        return v


class StorySubmissionResult(BaseModel):
    """
    <crc>
    responsibilities:
      - Represent successful story submission
    collaborators: []
    </crc>
    """

    story_id: str
    message: str = "Story submitted successfully"


class StorySubmissionService:
    """
    <crc>
    responsibilities:
      - Accept valid participant stories into the system
      - Translate submission data into the story domain model
    collaborators:
      - StoragePort
      - Story
    </crc>
    """

    def __init__(self, storage: StoragePort, valid_triad_ids: set[str] | None = None):
        """
        Initialize story submission service.

        Args:
            storage: Storage port for persisting stories
            valid_triad_ids: Allowlist of known triad IDs from config.
                             If None, signifier ID membership is not validated.
        """
        self.storage = storage
        self.valid_triad_ids = valid_triad_ids

    def submit_story(self, request: StorySubmissionRequest) -> StorySubmissionResult:
        """
        Submit a new story.

        Args:
            request: Story submission request with validated data

        Returns:
            StorySubmissionResult with story ID

        Raises:
            ValueError: If signifier IDs not in allowlist
            StorageError: If storage operation fails
        """
        # Validate signifier IDs against config allowlist
        if self.valid_triad_ids is not None:
            submitted_ids = {r.signifier_id for r in request.signification.responses}
            unknown = submitted_ids - self.valid_triad_ids
            if unknown:
                raise ValueError(f"Unknown signifier IDs: {', '.join(sorted(unknown))}")

        story_id = str(uuid4())

        # Convert signification
        signification = StorySignification(
            headline=request.signification.headline,
            responses=[
                TriadResponseItem(
                    kind=r.kind,
                    signifier_id=r.signifier_id,
                    coordinates=TriadCoordinates(x=r.coordinates.x, y=r.coordinates.y),
                )
                for r in request.signification.responses
            ],
        )

        # Convert context metadata if present
        context = None
        if request.context:
            context = ContextMetadata(
                department=request.context.department,
                role=request.context.role,
                tool_context=request.context.tool_context,
            )

        # Convert participant metadata if present
        participant = None
        if request.participant:
            participant = ParticipantMetadata(
                user_pseudonym=request.participant.user_pseudonym,
            )

        story = Story(
            id=story_id,
            story_text=request.story_text,
            schema_version=2,
            triads=[],
            signification=signification,  # always set; required field
            context=context,
            participant=participant,
            timestamp=datetime.now(UTC),
            processing_status="pending",
        )

        saved_id = self.storage.save_story(story)
        return StorySubmissionResult(story_id=saved_id)
