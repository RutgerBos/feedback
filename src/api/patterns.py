"""
Patterns API endpoints.

Query stories by entity or theme.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.stories import StoryListResponse, _story_to_response, get_graph, get_storage
from src.ports.errors import GraphError, NotFoundError
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


class CorrelationPair(BaseModel):
    entity_a: str
    entity_b: str
    co_count: int
    jaccard: float
    sample_story_ids: list[str]


class CorrelationListResponse(BaseModel):
    pairs: list[CorrelationPair]


class ThemeEntry(BaseModel):
    name: str
    story_count: int
    sample_story_ids: list[str]


class ThemeListResponse(BaseModel):
    themes: list[ThemeEntry]


@router.get("/themes", response_model=ThemeListResponse)
async def get_themes(
    limit: int = Query(default=25, ge=1, le=100),
    sample_size: int = Query(default=3, ge=1, le=10),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    service: PatternQueryService = Depends(get_pattern_query_service),
) -> ThemeListResponse:
    """
    Return themes ranked by story count with sample story IDs per theme.

    Optionally filtered by ISO8601 date strings (from_date, to_date).
    """
    # Normalize bare YYYY-MM-DD strings so Neo4j lexicographic comparison includes
    # stories timestamped as full ISO datetimes on those boundary dates.
    if from_date and len(from_date) == 10:
        from_date = from_date + "T00:00:00"
    if to_date and len(to_date) == 10:
        to_date = to_date + "T23:59:59"

    try:
        result = service.query_themes(
            limit=limit,
            sample_size=sample_size,
            from_date=from_date,
            to_date=to_date,
        )
    except GraphError as e:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from e

    return ThemeListResponse(
        themes=[ThemeEntry(**t) for t in result.themes]
    )


@router.get("/correlations", response_model=CorrelationListResponse)
async def get_correlations(
    limit: int = Query(default=25, ge=1, le=100),
    sample_size: int = Query(default=3, ge=1, le=10),
    threshold: float = Query(default=0.0, ge=0.0, le=1.0),
    entity_type: str | None = Query(default=None),
    service: PatternQueryService = Depends(get_pattern_query_service),
) -> CorrelationListResponse:
    """
    Return entity pairs ranked by Jaccard co-occurrence strength.

    threshold filters out weak correlations; entity_type restricts both entities to that type.
    """
    try:
        result = service.query_correlations(
            limit=limit,
            sample_size=sample_size,
            threshold=threshold,
            entity_type=entity_type,
        )
    except GraphError as e:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from e

    return CorrelationListResponse(
        pairs=[
            CorrelationPair(
                entity_a=p.entity_a,
                entity_b=p.entity_b,
                co_count=p.co_count,
                jaccard=p.jaccard,
                sample_story_ids=p.sample_story_ids,
            )
            for p in result.pairs
        ]
    )


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
    except NotFoundError as e:
        raise HTTPException(status_code=503, detail="Story data inconsistency — retry later") from e

    return StoryListResponse(
        stories=[_story_to_response(s) for s in result.stories],
        total=result.total,
        limit=limit,
        offset=offset,
    )
