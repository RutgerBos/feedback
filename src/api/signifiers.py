"""Evidence-first spatial drill-down endpoints for signifier responses."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.api.stories import ContextResponse, SignifierCoordinatesResponse, get_storage
from src.domain.geometry import is_point_in_triad_triangle
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
            if not is_point_in_triad_triangle(point.x, point.y):
                raise ValueError("polygon points must lie inside the triad triangle")
        doubled_area = sum(
            point.x * self.points[(index + 1) % len(self.points)].y
            - self.points[(index + 1) % len(self.points)].x * point.y
            for index, point in enumerate(self.points)
        )
        if abs(doubled_area) <= 1e-12:
            raise ValueError("polygon must enclose a non-zero area")
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
    context_metadata: ContextResponse | None
    themes: list[str] | None = None
    entities: list[dict[str, str]] | None = None


class SpatialStoryResponse(BaseModel):
    stories: list[SpatialStoryItem]
    limit: int
    offset: int


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
        context_metadata=ContextResponse(
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
