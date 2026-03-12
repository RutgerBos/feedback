"""
Stories API endpoints.

Handles story submission and retrieval.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.services.story_submission import (
    StorySubmissionService,
    StorySubmissionRequest,
    StorySubmissionResult,
)
from src.ports.storage import StoragePort
from src.adapters.mongodb_storage import MongoDBStorageAdapter, NotFoundError
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


def get_submission_service(storage: StoragePort = Depends(get_storage)) -> StorySubmissionService:
    """
    Dependency that provides story submission service.

    Args:
        storage: Injected storage port

    Returns:
        StorySubmissionService: Configured service
    """
    return StorySubmissionService(storage)


@router.post("", response_model=StorySubmissionResult, status_code=201)
async def submit_story(
    request: StorySubmissionRequest,
    service: StorySubmissionService = Depends(get_submission_service),
) -> StorySubmissionResult:
    """
    Submit a new story with triad placements.

    Args:
        request: Story submission data
        service: Injected story submission service

    Returns:
        StorySubmissionResult with story ID

    Raises:
        HTTPException 400: If validation fails
        HTTPException 500: If storage fails
    """
    try:
        result = service.submit_story(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the error in production
        raise HTTPException(status_code=500, detail="Failed to submit story")


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
        return StoryResponse(
            id=story.id,
            story_text=story.story_text,
            triads=[
                TriadResponse(
                    triad_id=p.triad_id,
                    x=p.coordinates.x,
                    y=p.coordinates.y,
                )
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
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")
