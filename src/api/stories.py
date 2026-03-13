"""
Stories API endpoints.

Handles story submission and retrieval.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from src.services.story_submission import (
    StorySubmissionService,
    StorySubmissionRequest,
    StorySubmissionResult,
)
from src.services.entity_extraction import EntityExtractionService
from src.ports.storage import StoragePort
from src.ports.llm import LLMPort, EntityExtraction
from src.ports.errors import NotFoundError, LLMError
from src.adapters.mongodb_storage import MongoDBStorageAdapter
from pymongo import MongoClient


router = APIRouter(prefix="/api/stories", tags=["stories"])


class TriadResponse(BaseModel):
    triad_id: str
    x: float
    y: float


class MetadataResponse(BaseModel):
    user_pseudonym: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    tool_context: Optional[str] = None


class StoryResponse(BaseModel):
    id: str
    story_text: str
    triads: List[TriadResponse]
    metadata: Optional[MetadataResponse] = None
    timestamp: datetime
    processing_status: str


class StoryListResponse(BaseModel):
    stories: List[StoryResponse]
    total: int
    limit: int
    offset: int


def get_storage() -> StoragePort:
    """
    Dependency that provides storage port.

    Returns:
        StoragePort: MongoDB storage adapter

    Notes:
        - Creates MongoDB client and database connection
        - In production, should use connection pooling
        - Connection details from environment/config
    """
    # TODO: Move connection details to configuration
    client = MongoClient("mongodb://admin:password@mongodb:27017/")
    db = client["feedback"]
    return MongoDBStorageAdapter(db)


class _NoOpLLM(LLMPort):
    """
    Fallback LLM used when no provider is configured.

    Raises LLMError on all calls so EntityExtractionService sets
    processing_status='failed' rather than silently marking stories as
    'processed' with empty entities. This keeps 'pending' reserved for
    stories that have not yet been attempted.
    """

    def extract_entities(self, story_text: str) -> EntityExtraction:
        raise LLMError("No LLM provider configured — override get_llm dependency")

    def extract_themes(self, story_text: str) -> list:
        raise LLMError("No LLM provider configured")

    def extract_relationships(self, story_text: str) -> list:
        raise LLMError("No LLM provider configured")


def get_llm() -> LLMPort:
    """
    Dependency that provides LLM port.

    Returns a no-op implementation by default. Override in tests or production
    with a real provider via app.dependency_overrides[get_llm].
    """
    return _NoOpLLM()


def get_entity_extraction_service(
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> EntityExtractionService:
    """Dependency that provides entity extraction service."""
    return EntityExtractionService(storage=storage, llm=llm)


def get_submission_service(
    request: Request,
    storage: StoragePort = Depends(get_storage),
) -> StorySubmissionService:
    """
    Dependency that provides story submission service.

    Args:
        request: FastAPI request (used to access app.state.triad_config)
        storage: Injected storage port

    Returns:
        StorySubmissionService: Configured service with triad ID allowlist
    """
    triad_config = getattr(request.app.state, "triad_config", None)
    valid_triad_ids = {t.id for t in triad_config.triads} if triad_config else None
    return StorySubmissionService(storage, valid_triad_ids=valid_triad_ids)


@router.post("", response_model=StorySubmissionResult, status_code=201)
async def submit_story(
    request: StorySubmissionRequest,
    background_tasks: BackgroundTasks,
    service: StorySubmissionService = Depends(get_submission_service),
    entity_service: EntityExtractionService = Depends(get_entity_extraction_service),
) -> StorySubmissionResult:
    """
    Submit a new story with triad placements.

    Args:
        request: Story submission data
        background_tasks: FastAPI background task manager
        service: Injected story submission service
        entity_service: Injected entity extraction service

    Returns:
        StorySubmissionResult with story ID

    Raises:
        HTTPException 400: If validation fails
        HTTPException 500: If storage fails
    """
    try:
        result = service.submit_story(request)
        background_tasks.add_task(entity_service.extract_for_story, result.story_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the error in production
        raise HTTPException(status_code=500, detail="Failed to submit story")


def _story_to_response(story) -> StoryResponse:
    return StoryResponse(
        id=story.id,
        story_text=story.story_text,
        triads=[
            TriadResponse(triad_id=p.triad_id, x=p.coordinates.x, y=p.coordinates.y)
            for p in story.triads
        ],
        metadata=MetadataResponse(
            user_pseudonym=story.metadata.user_pseudonym,
            department=story.metadata.department,
            role=story.metadata.role,
            tool_context=story.metadata.tool_context,
        ) if story.metadata else None,
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
    return StoryListResponse(
        stories=[_story_to_response(s) for s in stories],
        total=storage.count_stories(),
        limit=limit,
        offset=offset,
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
    """
    try:
        story = storage.get_story(story_id)
        return _story_to_response(story)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")
