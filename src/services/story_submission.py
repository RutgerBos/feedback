"""
Story submission service.

Coordinates the submission of new stories, including validation,
ID generation, and persistence.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from src.domain.models import (
    ContextMetadata,
    ParticipantMetadata,
    Story,
    StoryMetadata,
    StorySignification,
    TriadCoordinates,
    TriadPlacement,
    TriadResponseItem,
)
from src.ports.storage import StoragePort


class StorySubmissionRequest(BaseModel):
    """
    Request model for story submission.

    Responsibilities:
    - Hold and validate story submission data
    - Support both V1 (triads + metadata) and V2 (signification + context + participant) paths

    Notes:
    - Used as input to StorySubmissionService
    - Validates on construction via Pydantic
    - V1: triads list with dict entries; metadata flat dict
    - V2: signification dict, context dict, participant dict; triads may be empty
    """

    story_text: str = Field(..., min_length=50, max_length=2000)
    triads: list[dict[str, Any]] = Field(default_factory=list)
    # V1 compat
    metadata: dict[str, str | None] | None = None
    # V2 fields
    signification: dict[str, Any] | None = None
    context: dict[str, str | None] | None = None
    participant: dict[str, str | None] | None = None

    @field_validator("triads")
    @classmethod
    def validate_triad_structure(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure each triad has required fields."""
        for triad in v:
            if "triad_id" not in triad:
                raise ValueError("Each triad must have a triad_id")
            if "x" not in triad or "y" not in triad:
                raise ValueError("Each triad must have x and y coordinates")
            # Validate coordinate range
            if not (0.0 <= triad["x"] <= 1.0):
                raise ValueError("Coordinate x must be between 0 and 1")
            if not (0.0 <= triad["y"] <= 1.0):
                raise ValueError("Coordinate y must be between 0 and 1")
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
    - valid_triad_ids: when provided, submitted triad_ids must be in the set
    """

    def __init__(self, storage: StoragePort, valid_triad_ids: set[str] | None = None):
        """
        Initialize story submission service.

        Args:
            storage: Storage port for persisting stories
            valid_triad_ids: Allowlist of known triad IDs from config.
                             If None, triad ID membership is not validated.
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
            ValueError: If validation fails (caught by Pydantic)
            StorageError: If storage operation fails
        """
        # Validate signifier IDs against config allowlist (covers both triads and signification)
        if self.valid_triad_ids is not None:
            submitted_ids = {t["triad_id"] for t in request.triads}
            if request.signification:
                submitted_ids |= {
                    r["signifier_id"]
                    for r in request.signification.get("responses", [])
                }
            unknown = submitted_ids - self.valid_triad_ids
            if unknown:
                raise ValueError(f"Unknown triad IDs: {', '.join(sorted(unknown))}")

        # Generate UUID for story
        story_id = str(uuid4())

        # Convert request triads to domain model
        triad_placements = [
            TriadPlacement(
                triad_id=t["triad_id"],
                coordinates=TriadCoordinates(x=t["x"], y=t["y"]),
            )
            for t in request.triads
        ]

        # Convert V1 metadata if present
        metadata = None
        if request.metadata:
            metadata = StoryMetadata(
                user_pseudonym=request.metadata.get("user_pseudonym"),
                department=request.metadata.get("department"),
                role=request.metadata.get("role"),
                tool_context=request.metadata.get("tool_context"),
            )

        # Convert V2 signification if present
        signification = None
        if request.signification:
            sig = request.signification
            responses = [
                TriadResponseItem(
                    kind=r["kind"],
                    signifier_id=r["signifier_id"],
                    coordinates=TriadCoordinates(
                        x=r["coordinates"]["x"], y=r["coordinates"]["y"]
                    ),
                )
                for r in sig.get("responses", [])
            ]
            signification = StorySignification(
                headline=sig.get("headline"),
                responses=responses,
            )

        # Convert V2 context metadata if present
        context = None
        if request.context:
            context = ContextMetadata(
                department=request.context.get("department"),
                role=request.context.get("role"),
                tool_context=request.context.get("tool_context"),
            )

        # Convert V2 participant metadata if present
        participant = None
        if request.participant:
            participant = ParticipantMetadata(
                user_pseudonym=request.participant.get("user_pseudonym"),
            )

        # Create story domain model (V2)
        story = Story(
            id=story_id,
            story_text=request.story_text,
            schema_version=2,
            triads=triad_placements,
            metadata=metadata,
            signification=signification,
            context=context,
            participant=participant,
            timestamp=datetime.now(UTC),
            processing_status="pending",
        )

        # Save via storage port
        saved_id = self.storage.save_story(story)

        return StorySubmissionResult(story_id=saved_id)
