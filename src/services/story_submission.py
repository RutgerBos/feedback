"""
Story submission service.

Coordinates the submission of new stories, including validation,
ID generation, and persistence.
"""

from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

from src.ports.storage import StoragePort
from src.domain.models import Story, TriadPlacement, TriadCoordinates, StoryMetadata


class StorySubmissionRequest(BaseModel):
    """
    Request model for story submission.

    Responsibilities:
    - Hold and validate story submission data
    - Ensure all required fields are present
    - Validate field constraints

    Notes:
    - Used as input to StorySubmissionService
    - Validates on construction via Pydantic
    - Triads represented as simple dicts for API convenience
    """

    story_text: str = Field(..., min_length=50, max_length=2000)
    triads: List[Dict[str, Any]] = Field(..., min_length=3, max_length=3)
    metadata: Optional[Dict[str, Optional[str]]] = None

    @field_validator("triads")
    @classmethod
    def validate_triad_structure(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    """

    def __init__(self, storage: StoragePort):
        """
        Initialize story submission service.

        Args:
            storage: Storage port for persisting stories
        """
        self.storage = storage

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

        # Convert metadata if present
        metadata = None
        if request.metadata:
            metadata = StoryMetadata(
                user_pseudonym=request.metadata.get("user_pseudonym"),
                department=request.metadata.get("department"),
                role=request.metadata.get("role"),
                tool_context=request.metadata.get("tool_context"),
            )

        # Create story domain model
        story = Story(
            id=story_id,
            story_text=request.story_text,
            triads=triad_placements,
            metadata=metadata,
            timestamp=datetime.now(timezone.utc),
            processing_status="pending",
        )

        # Save via storage port
        saved_id = self.storage.save_story(story)

        return StorySubmissionResult(story_id=saved_id)
