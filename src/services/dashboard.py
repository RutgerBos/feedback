"""
DashboardService: aggregates theme and entity statistics from stored stories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from src.ports.storage import StoragePort

if TYPE_CHECKING:
    from src.domain.models import Story

_MAX_STORIES = 500  # upper bound for aggregation scan
_TOP_N = 10        # max items in top_themes / top_entities


@dataclass
class DashboardData:
    """
    Responsibilities:
    - Hold aggregated dashboard statistics

    Collaborators:
    - None (value object)

    Notes:
    - top_themes and top_entities are sorted by count descending, capped at 10
    - recent_story_ids is a short list of the most recently loaded story IDs
    - total_stories reflects stories within the requested date range
    """

    total_stories: int
    top_themes: list[dict] = field(default_factory=list)
    top_entities: list[dict] = field(default_factory=list)
    recent_story_ids: list[str] = field(default_factory=list)


class DashboardService:
    """
    Responsibilities:
    - Aggregate theme and entity frequencies from stored stories
    - Apply optional date range filter
    - Return top-N themes and entities sorted by frequency

    Collaborators:
    - StoragePort (to load stories for aggregation)

    Notes:
    - Loads up to 500 stories for aggregation (MVP scope)
    - Does not modify StoragePort interface
    - Date filtering is applied in Python after loading
    """

    def __init__(self, storage: StoragePort) -> None:
        self._storage = storage

    def get_data(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> DashboardData:
        """
        Aggregate dashboard statistics, optionally filtered by date range.

        Args:
            from_date: Inclusive lower bound on story timestamp (UTC)
            to_date:   Inclusive upper bound on story timestamp (UTC)

        Returns:
            DashboardData with totals, top themes, top entities, recent IDs
        """
        stories = self._storage.list_stories(limit=_MAX_STORIES, offset=0)

        # Apply date filter — normalise to offset-naive UTC for comparison
        def _naive(dt: datetime) -> datetime:
            return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

        def _story_ts(s: Story) -> datetime:
            return _naive(s.timestamp)

        if from_date is not None:
            fd = _naive(from_date)
            stories = [s for s in stories if _story_ts(s) >= fd]
        if to_date is not None:
            td = _naive(to_date)
            stories = [s for s in stories if _story_ts(s) <= td]

        if not stories:
            return DashboardData(total_stories=0)

        # Aggregate themes
        theme_counts: dict[str, int] = {}
        for story in stories:
            for theme in story.themes:
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Aggregate entities (by name)
        entity_counts: dict[str, int] = {}
        for story in stories:
            for entity in story.entities:
                name = entity.get("name", "")
                if name:
                    entity_counts[name] = entity_counts.get(name, 0) + 1

        top_themes = [
            {"name": name, "count": count}
            for name, count in sorted(theme_counts.items(), key=lambda x: -x[1])
        ][:_TOP_N]

        top_entities = [
            {"name": name, "count": count}
            for name, count in sorted(entity_counts.items(), key=lambda x: -x[1])
        ][:_TOP_N]

        recent_story_ids = [s.id for s in stories[:5]]

        return DashboardData(
            total_stories=len(stories),
            top_themes=top_themes,
            top_entities=top_entities,
            recent_story_ids=recent_story_ids,
        )
