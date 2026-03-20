"""
Patterns API endpoints.

Query stories by entity or theme.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.stories import StoryListResponse, _story_to_response, get_graph, get_storage
from src.ports.errors import GraphError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort
from src.services.pattern_query import PatternQueryService

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


def get_pattern_query_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> PatternQueryService:
    """Dependency that provides the pattern query service."""
    return PatternQueryService(graph=graph, storage=storage)


@router.get("/by-entity/{entity_name}", response_model=StoryListResponse)
async def query_by_entity(
    entity_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: PatternQueryService = Depends(get_pattern_query_service),
) -> StoryListResponse:
    """
    Return stories that mention the given entity.

    Args:
        entity_name: Entity name to search (case-insensitive)
        limit: Maximum stories to return (default 20, max 100)
        offset: Number of stories to skip for pagination

    Returns:
        StoryListResponse with matching stories and total count

    Raises:
        HTTPException 503: If the graph database is unavailable
    """
    try:
        result = service.query_by_entity(entity_name, limit=limit, offset=offset)
    except GraphError as e:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from e

    return StoryListResponse(
        stories=[_story_to_response(s) for s in result.stories],
        total=result.total,
        limit=limit,
        offset=offset,
    )
