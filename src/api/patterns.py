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
from src.services.clustering import ClusteringService
from src.services.pattern_query import PatternQueryService
from src.services.temporal import TemporalService

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


def get_pattern_query_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> PatternQueryService:
    """Dependency that provides the pattern query service."""
    return PatternQueryService(graph=graph, storage=storage)


def get_clustering_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> ClusteringService:
    """Dependency that provides the clustering service."""
    return ClusteringService(graph=graph, storage=storage)


def get_temporal_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
) -> TemporalService:
    """Dependency that provides the temporal analysis service."""
    return TemporalService(graph=graph, storage=storage)


class WindowedCount(BaseModel):
    window: str
    count: int


class ThemeTimeline(BaseModel):
    theme: str
    windows: list[WindowedCount]


class EntityTimeline(BaseModel):
    entity: str
    windows: list[WindowedCount]


class WindowedCentroid(BaseModel):
    window: str
    center_x: float
    center_y: float
    story_count: int


class TriadDrift(BaseModel):
    triad_id: str
    centroids: list[WindowedCentroid]


class TemporalResponse(BaseModel):
    windows: list[str]
    theme_frequency: list[ThemeTimeline]
    entity_frequency: list[EntityTimeline]
    triad_drift: list[TriadDrift]


class ClusterEntry(BaseModel):
    story_ids: list[str]
    center_x: float
    center_y: float
    top_themes: list[str]
    top_entities: list[str]


class ClusterResponse(BaseModel):
    clusters: list[ClusterEntry]


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


@router.get("/clusters", response_model=ClusterResponse)
async def get_clusters(
    triad_id: str = Query(...),
    service: ClusteringService = Depends(get_clustering_service),
) -> ClusterResponse:
    """
    Return Louvain community clusters for stories in the given triad's proximity graph.

    Args:
        triad_id: The triad whose proximity graph to cluster on

    Returns:
        ClusterResponse with one ClusterEntry per community

    Raises:
        HTTPException 503: If the GDS query fails
    """
    try:
        result = service.cluster_by_triad(triad_id)
    except GraphError as e:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from e
    except NotFoundError as e:
        raise HTTPException(status_code=503, detail="Story data inconsistency — retry later") from e

    return ClusterResponse(
        clusters=[
            ClusterEntry(
                story_ids=c.story_ids,
                center_x=c.center_x,
                center_y=c.center_y,
                top_themes=c.top_themes,
                top_entities=c.top_entities,
            )
            for c in result.clusters
        ]
    )


@router.get("/temporal", response_model=TemporalResponse)
async def get_temporal(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    window_size: str = Query(default="month", pattern="^(month|day)$"),
    theme: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    service: TemporalService = Depends(get_temporal_service),
) -> TemporalResponse:
    """
    Return time-windowed theme/entity frequency and triad coordinate drift.

    Args:
        from_date:   ISO8601 lower bound (inclusive); bare YYYY-MM-DD normalised to start-of-day
        to_date:     ISO8601 upper bound (inclusive); bare YYYY-MM-DD normalised to end-of-day
        window_size: Bucket size — "month" (YYYY-MM) or "day" (YYYY-MM-DD)
        theme:       Restrict theme_frequency and drift to this theme
        entity:      Restrict entity_frequency and drift to this entity

    Returns:
        TemporalResponse with windows, theme_frequency, entity_frequency, triad_drift

    Raises:
        HTTPException 503: If the graph database is unavailable
    """
    if from_date and len(from_date) == 10:
        from_date = from_date + "T00:00:00"
    if to_date and len(to_date) == 10:
        to_date = to_date + "T23:59:59"

    try:
        result = service.query_temporal(
            from_date=from_date,
            to_date=to_date,
            window_size=window_size,
            theme=theme,
            entity=entity,
        )
    except GraphError as e:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from e
    except NotFoundError as e:
        raise HTTPException(status_code=503, detail="Story data inconsistency — retry later") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {e}") from e

    return TemporalResponse(
        windows=result.windows,
        theme_frequency=[
            ThemeTimeline(
                theme=t.theme,
                windows=[WindowedCount(window=w.window, count=w.count) for w in t.windows],
            )
            for t in result.theme_frequency
        ],
        entity_frequency=[
            EntityTimeline(
                entity=e.entity,
                windows=[WindowedCount(window=w.window, count=w.count) for w in e.windows],
            )
            for e in result.entity_frequency
        ],
        triad_drift=[
            TriadDrift(
                triad_id=d.triad_id,
                centroids=[
                    WindowedCentroid(
                        window=c.window,
                        center_x=c.center_x,
                        center_y=c.center_y,
                        story_count=c.story_count,
                    )
                    for c in d.centroids
                ],
            )
            for d in result.triad_drift
        ],
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
