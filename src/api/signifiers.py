"""Evidence-first spatial drill-down endpoints for signifier responses."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.api.stories import ContextResponse, SignifierCoordinatesResponse, get_storage
from src.domain.models import Story
from src.ports.errors import StorageError
from src.ports.storage import StoragePort

router = APIRouter(prefix="/api/signifiers", tags=["signifiers"])


class PolygonPoint(BaseModel):
    x: float
    y: float


class PolygonSelection(BaseModel):
    kind: Literal["polygon"]
    points: list[PolygonPoint] = Field(min_length=3)

    @model_validator(mode="after")
    def points_must_lie_in_triad_triangle(self) -> "PolygonSelection":
        """Reject bounding-box coordinates outside the rendered triangle."""
        for point in self.points:
            if not _inside_triad_triangle(point.x, point.y):
                raise ValueError("polygon points must lie inside the triad triangle")
        return self


class SpatialStoryQuery(BaseModel):
    selection: PolygonSelection
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    include_overlays: bool = False


class SpatialStoryItem(BaseModel):
    id: str
    headline: str | None
    story_excerpt: str
    coordinates: SignifierCoordinatesResponse
    timestamp: datetime
    context: ContextResponse | None
    themes: list[str] | None = None
    entities: list[dict[str, str]] | None = None


class SpatialStoryResponse(BaseModel):
    stories: list[SpatialStoryItem]
    limit: int
    offset: int


def _inside_triad_triangle(x: float, y: float) -> bool:
    """Match the UI triangle with vertices (0.5, 0), (0, 1), and (1, 1)."""
    return 0 <= y <= 1 and 0 <= x <= 1 and abs(x - 0.5) <= y / 2


def _to_spatial_item(
    story: Story, signifier_id: str, include_overlays: bool
) -> SpatialStoryItem:
    if story.signification is None:
        raise ValueError("Spatial query returned a story without signification")
    response = next(
        item
        for item in story.signification.responses
        if item.signifier_id == signifier_id
    )
    return SpatialStoryItem(
        id=story.id,
        headline=story.signification.headline,
        story_excerpt=story.story_text[:300],
        coordinates=SignifierCoordinatesResponse(
            x=response.coordinates.x, y=response.coordinates.y
        ),
        timestamp=story.timestamp,
        context=ContextResponse(
            department=story.context.department,
            role=story.context.role,
            tool_context=story.context.tool_context,
        )
        if story.context
        else None,
        themes=story.themes if include_overlays else None,
        entities=story.entities if include_overlays else None,
    )


@router.post(
    "/{signifier_id}/stories/query",
    response_model=SpatialStoryResponse,
    response_model_exclude_none=True,
)
def query_signifier_stories(
    signifier_id: str,
    query: SpatialStoryQuery,
    storage: StoragePort = Depends(get_storage),
) -> SpatialStoryResponse:
    """Return participant evidence selected within a signifier-space polygon."""
    points = [(point.x, point.y) for point in query.selection.points]
    try:
        stories = storage.find_stories_in_polygon(
            signifier_id, points, limit=query.limit, offset=query.offset
        )
    except StorageError as exc:
        raise HTTPException(status_code=503, detail="Story data unavailable") from exc
    return SpatialStoryResponse(
        stories=[
            _to_spatial_item(story, signifier_id, query.include_overlays)
            for story in stories
        ],
        limit=query.limit,
        offset=query.offset,
    )
