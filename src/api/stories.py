"""
Stories API endpoints.

Handles story submission and retrieval.
"""

from fastapi import APIRouter, HTTPException, Depends
from src.services.story_submission import (
    StorySubmissionService,
    StorySubmissionRequest,
    StorySubmissionResult,
)
from src.ports.storage import StoragePort
from src.adapters.mongodb_storage import MongoDBStorageAdapter
from pymongo import MongoClient


router = APIRouter(prefix="/api/stories", tags=["stories"])


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
