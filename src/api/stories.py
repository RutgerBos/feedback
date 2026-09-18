"""
Stories API endpoints.

Handles story submission and retrieval.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.composition import (
    get_queue,
    get_storage,
    get_submission_service,
)
from src.domain.models import Story
from src.ports.errors import NotFoundError
from src.ports.storage import StoragePort
from src.services.story_submission import (
    StorySubmissionRequest,
    StorySubmissionResult,
    StorySubmissionService,
)
from src.workers.worker_queue import WorkerQueue

router = APIRouter(prefix="/api/stories", tags=["stories"])
logger = logging.getLogger(__name__)


class SignifierCoordinatesResponse(BaseModel):
    x: float
    y: float


class SignifierResponseItem(BaseModel):
    kind: str
    signifier_id: str
    coordinates: SignifierCoordinatesResponse


class SignificationResponse(BaseModel):
    headline: str | None = None
    responses: list[SignifierResponseItem]


class ContextResponse(BaseModel):
    department: str | None = None
    role: str | None = None
    tool_context: str | None = None


class ParticipantResponse(BaseModel):
    user_pseudonym: str | None = None


class StoryResponse(BaseModel):
    id: str
    story_text: str
    signification: SignificationResponse | None = None
    context: ContextResponse | None = None
    participant: ParticipantResponse | None = None
    timestamp: datetime
    processing_status: str


class StoryListResponse(BaseModel):
    stories: list[StoryResponse]
    total: int
    limit: int
    offset: int


@router.post("", response_model=StorySubmissionResult, status_code=201)
async def submit_story(
    request: StorySubmissionRequest,
    service: StorySubmissionService = Depends(get_submission_service),
    queue: WorkerQueue = Depends(get_queue),
) -> StorySubmissionResult:
    """
    Submit a new story with triad placements.

    Args:
        request: Story submission data
        service: Injected story submission service
        queue: Injected worker queue

    Returns:
        StorySubmissionResult with story ID

    Raises:
        HTTPException 400: If validation fails
        HTTPException 500: If storage fails
    """
    try:
        result = service.submit_story(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to submit story") from e

    try:
        queue.enqueue(result.story_id)
    except Exception:
        # MongoDB is the source of truth. The worker's periodic sweep will recover
        # persisted stories after Redis becomes available again.
        logger.exception("Story %s was saved but could not be enqueued", result.story_id)
    return result


def _story_to_response(story: Story) -> StoryResponse:
    signification = None
    if story.signification:
        signification = SignificationResponse(
            headline=story.signification.headline,
            responses=[
                SignifierResponseItem(
                    kind=r.kind,
                    signifier_id=r.signifier_id,
                    coordinates=SignifierCoordinatesResponse(x=r.coordinates.x, y=r.coordinates.y),
                )
                for r in story.signification.responses
            ],
        )
    context = None
    if story.context:
        context = ContextResponse(
            department=story.context.department,
            role=story.context.role,
            tool_context=story.context.tool_context,
        )
    participant = None
    if story.participant:
        participant = ParticipantResponse(user_pseudonym=story.participant.user_pseudonym)
    return StoryResponse(
        id=story.id,
        story_text=story.story_text,
        signification=signification,
        context=context,
        participant=participant,
        timestamp=story.timestamp,
        processing_status=story.processing_status,
    )


@router.get("", response_model=StoryListResponse)
async def list_stories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    storage: StoragePort = Depends(get_storage),
) -> StoryListResponse:
    """
    List all stories with pagination.

    Args:
        limit: Maximum number of stories to return (default 20)
        offset: Number of stories to skip (default 0)
        storage: Injected storage port

    Returns:
        StoryListResponse with stories and pagination info
    """
    stories = storage.list_stories(limit=limit, offset=offset)
    v2_stories = [s for s in stories if s.signification is not None]
    return StoryListResponse(
        stories=[_story_to_response(s) for s in v2_stories],
        total=storage.count_stories(),
        limit=limit,
        offset=offset,
    )


def _require_v2(story: "Story") -> None:
    """Raise 422 if the story is a V1 document (no signification)."""
    if story.signification is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Story {story.id} is a V1 document and has not been migrated. "
                "Run the V1→V2 migration script before accessing this story."
            ),
        )


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: str,
    storage: StoragePort = Depends(get_storage),
) -> StoryResponse:
    """
    Retrieve a story by ID.

    Args:
        story_id: Unique identifier of the story
        storage: Injected storage port

    Returns:
        StoryResponse with all story fields

    Raises:
        HTTPException 404: If story not found
        HTTPException 422: If story is a V1 document (not yet migrated)
    """
    try:
        story = storage.get_story(story_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Story not found: {story_id}") from e
    _require_v2(story)
    return _story_to_response(story)
