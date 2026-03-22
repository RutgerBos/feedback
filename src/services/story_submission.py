"""
Story submission service.

Coordinates the submission of new stories, including validation,
ID generation, and persistence.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

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


class TriadResponseRequest(BaseModel):
    """One response placement in a signification."""

    kind: Literal["triad"] = "triad"
    signifier_id: str
    coordinates: CoordinatesRequest


class SignificationRequest(BaseModel):
    """V2 signification block sent by the client."""

    headline: str | None = None
    responses: list[TriadResponseRequest] = Field(default_factory=list)


class StorySubmissionRequest(BaseModel):
    """
    Request model for story submission.

    Responsibilities:
    - Hold and validate story submission data

    Notes:
    - Used as input to StorySubmissionService
    - Validates on construction via Pydantic
    - triads field is kept to provide a clear rejection message for old V1 clients
    - signification, context, participant are the V2 fields
    """

    story_text: str = Field(..., min_length=50, max_length=2000)
    triads: list[dict[str, Any]] = Field(default_factory=list)
    signification: SignificationRequest | None = None
    context: dict[str, str | None] | None = None
    participant: dict[str, str | None] | None = None

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
    Result of story submission.

    Responsibilities:
    - Hold submission result data
    - Provide story ID to caller

    Notes:
    - Simple data holder
    - Returned from StorySubmissionService
    """

    story_id: str
    message: str = "Story submitted successfully"


class StorySubmissionService:
    """
    Responsibilities:
    - Coordinate story submission workflow
    - Generate story ID (UUID)
    - Convert request data to domain model
    - Delegate storage to StoragePort

    Collaborators:
    - StoragePort (interface)
    - Story (domain model)
    - StorySubmissionRequest (input)
    - StorySubmissionResult (output)

    Notes:
    - Pure coordination - no business logic
    - All validation delegated to domain models and request model
    - Doesn't know about MongoDB or specific storage
    - valid_triad_ids: when provided, submitted signifier_ids must be in the set
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
        if self.valid_triad_ids is not None and request.signification:
            submitted_ids = {r.signifier_id for r in request.signification.responses}
            unknown = submitted_ids - self.valid_triad_ids
            if unknown:
                raise ValueError(f"Unknown triad IDs: {', '.join(sorted(unknown))}")

        story_id = str(uuid4())

        # Convert signification
        signification = None
        if request.signification:
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
                department=request.context.get("department"),
                role=request.context.get("role"),
                tool_context=request.context.get("tool_context"),
            )

        # Convert participant metadata if present
        participant = None
        if request.participant:
            participant = ParticipantMetadata(
                user_pseudonym=request.participant.get("user_pseudonym"),
            )

        story = Story(
            id=story_id,
            story_text=request.story_text,
            schema_version=2,
            triads=[],
            signification=signification,
            context=context,
            participant=participant,
            timestamp=datetime.now(UTC),
            processing_status="pending",
        )

        saved_id = self.storage.save_story(story)
        return StorySubmissionResult(story_id=saved_id)
