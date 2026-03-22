"""
Stories API endpoints.

Handles story submission and retrieval.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from src.adapters.mongodb_storage import MongoDBStorageAdapter
from src.adapters.neo4j_graph import Neo4jGraphAdapter
from src.domain.models import SentimentAnalysis, Story, TriadCoordinates, TriadPlacement
from src.ports.errors import LLMError, NotFoundError
from src.ports.graph import GraphPort
from src.ports.llm import EntityExtraction, LLMPort
from src.ports.storage import StoragePort
from src.services.entity_extraction import EntityExtractionService
from src.services.graph_projection import GraphProjectionService
from src.services.proximity import ProximityCalculationService
from src.services.sentiment_extraction import SentimentExtractionService
from src.services.story_submission import (
    StorySubmissionRequest,
    StorySubmissionResult,
    StorySubmissionService,
)

router = APIRouter(prefix="/api/stories", tags=["stories"])


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


def get_storage(request: Request) -> StoragePort:
    """
    Dependency that provides storage port.

    Reads the MongoClient singleton and database name from app.state,
    both set during application startup. No new client is created per request.

    Returns:
        StoragePort: MongoDB storage adapter
    """
    client = request.app.state.mongo_client
    db_name = request.app.state.settings.mongodb_database
    return MongoDBStorageAdapter(client[db_name])


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

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        raise LLMError("No LLM provider configured")

    def synthesize_insights(self, context):  # type: ignore[override]
        raise LLMError("No LLM provider configured — override get_llm dependency")

    def translate_query(self, question: str):  # type: ignore[override]
        raise LLMError("No LLM provider configured — override get_llm dependency")


def get_llm() -> LLMPort:
    """
    Dependency that provides LLM port.

    Reads LLM_PROVIDER from settings ('ollama', 'claude', or 'none').
    Falls back to _NoOpLLM if provider is 'none' or unrecognised.
    """
    from src.adapters.llm_factory import create_llm_provider
    from src.config.settings import Settings
    settings = Settings()
    provider = settings.llm_provider.lower()
    if provider == "none":
        return _NoOpLLM()
    try:
        return create_llm_provider({
            "provider": provider,
            "model": settings.llm_model,
            "base_url": settings.local_model_url,
        })
    except ValueError:
        return _NoOpLLM()


def get_graph(request: Request) -> GraphPort:
    """
    Dependency that provides graph port.

    Reads the Neo4j driver singleton from app.state set during startup.

    Returns:
        GraphPort: Neo4j graph adapter
    """
    driver = request.app.state.neo4j_driver
    return Neo4jGraphAdapter(driver=driver)


def get_proximity_service(
    request: Request,
    storage: StoragePort = Depends(get_storage),
    graph: GraphPort = Depends(get_graph),
) -> ProximityCalculationService:
    """Dependency that provides proximity calculation service."""
    threshold = request.app.state.settings.proximity_threshold
    return ProximityCalculationService(storage=storage, graph=graph, threshold=threshold)


def get_graph_projection_service(
    storage: StoragePort = Depends(get_storage),
    graph: GraphPort = Depends(get_graph),
    proximity: ProximityCalculationService = Depends(get_proximity_service),
) -> GraphProjectionService:
    """Dependency that provides graph projection service."""
    return GraphProjectionService(storage=storage, graph=graph, proximity=proximity)


def get_entity_extraction_service(
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
    graph_projection: GraphProjectionService = Depends(get_graph_projection_service),
) -> EntityExtractionService:
    """Dependency that provides entity extraction service with graph projection wired."""
    return EntityExtractionService(storage=storage, llm=llm, graph_projection=graph_projection)


def get_sentiment_extraction_service(
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> SentimentExtractionService:
    """Dependency that provides sentiment extraction service."""
    return SentimentExtractionService(storage=storage, llm=llm)


def _save_story_to_graph(story_id: str, storage: StoragePort, graph: GraphPort) -> None:
    """Read story from storage and persist as a graph node."""
    story = storage.get_story(story_id)
    triads = [
        TriadPlacement(
            triad_id=r.signifier_id,
            coordinates=TriadCoordinates(x=r.coordinates.x, y=r.coordinates.y),
        )
        for r in (story.signification.responses if story.signification else [])
    ]
    graph.save_story_node(
        story_id=story.id,
        triads=triads,
        timestamp=story.timestamp.isoformat(),
    )


def _process_story(
    story_id: str,
    storage: StoragePort,
    graph: GraphPort,
    entity_service: EntityExtractionService,
    sentiment_service: SentimentExtractionService,
) -> None:
    """
    Run all post-submission processing in deterministic order.

    Graph node must exist before entity extraction runs graph projection,
    so steps are chained sequentially here rather than scheduled independently.
    """
    _save_story_to_graph(story_id, storage, graph)
    entity_service.extract_for_story(story_id)
    sentiment_service.extract_for_story(story_id)


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
    sentiment_service: SentimentExtractionService = Depends(get_sentiment_extraction_service),
    storage: StoragePort = Depends(get_storage),
    graph: GraphPort = Depends(get_graph),
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
        background_tasks.add_task(_process_story, result.story_id, storage, graph, entity_service, sentiment_service)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Log the error in production
        raise HTTPException(status_code=500, detail="Failed to submit story") from e


@router.post("/{story_id}/reprocess", status_code=202)
async def reprocess_story(
    story_id: str,
    background_tasks: BackgroundTasks,
    entity_service: EntityExtractionService = Depends(get_entity_extraction_service),
    sentiment_service: SentimentExtractionService = Depends(get_sentiment_extraction_service),
    storage: StoragePort = Depends(get_storage),
    graph: GraphPort = Depends(get_graph),
) -> dict:
    """
    TEMPORARY: Re-run LLM processing for a story that previously failed.

    TODO: Remove once feedback-cv7 (background worker) is implemented.
    """
    try:
        storage.get_story(story_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Story not found")
    background_tasks.add_task(_process_story, story_id, storage, graph, entity_service, sentiment_service)
    return {"story_id": story_id, "status": "reprocessing"}


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
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Story not found: {story_id}") from e
