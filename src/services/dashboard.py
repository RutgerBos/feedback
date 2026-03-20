"""
DashboardService: aggregates theme and entity statistics from stored stories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.ports.storage import StoragePort

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
    - top_themes and top_entities are sorted by count descending, capped at _TOP_N
    - distinct_theme_count / distinct_entity_count are the full unique counts
    - sample_capped is True when the dataset exceeded _MAX_STORIES
    - total_stories reflects stories within the requested date range
    """

    total_stories: int
    top_themes: list[dict] = field(default_factory=list)
    top_entities: list[dict] = field(default_factory=list)
    recent_story_ids: list[str] = field(default_factory=list)
    distinct_theme_count: int = 0
    distinct_entity_count: int = 0
    sample_capped: bool = False


class DashboardService:
    """
    Responsibilities:
    - Aggregate theme and entity frequencies from stored stories
    - Apply optional date range filter
    - Return top-N themes and entities sorted by frequency

    Collaborators:
    - StoragePort (to load stories for aggregation)

    Notes:
    - Loads up to _MAX_STORIES stories for aggregation (MVP scope)
    - sample_capped flag is set when the full dataset exceeds _MAX_STORIES
    - Date filtering converts all timestamps to UTC before comparison
    - to_date is treated as end-of-day (23:59:59) when time is midnight
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
            from_date: Inclusive lower bound on story timestamp
            to_date:   Inclusive upper bound on story timestamp.
                       If time is midnight (00:00:00), adjusted to 23:59:59
                       so whole-day selections behave intuitively.

        Returns:
            DashboardData with totals, top themes, top entities, recent IDs
        """
        # Normalise a datetime to UTC-naive for storage comparison
        def _to_utc_naive(dt: datetime) -> datetime:
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)
            return dt

        fd = _to_utc_naive(from_date) if from_date is not None else None
        td = _to_utc_naive(to_date) if to_date is not None else None

        # Treat midnight to_date as end-of-day so date-only inputs include the full day
        if td is not None and td.hour == 0 and td.minute == 0 and td.second == 0:
            td = td + timedelta(days=1) - timedelta(seconds=1)

        total_in_range = self._storage.count_stories(from_date=fd, to_date=td)
        stories = self._storage.list_stories(limit=_MAX_STORIES, offset=0, from_date=fd, to_date=td)
        sample_capped = total_in_range > _MAX_STORIES

        if not stories:
            return DashboardData(total_stories=0, sample_capped=sample_capped)

        # Aggregate themes — count stories, not occurrences
        theme_counts: dict[str, int] = {}
        for story in stories:
            for theme in set(story.themes):
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Aggregate entities (by name) — count stories, not occurrences
        entity_counts: dict[str, int] = {}
        for story in stories:
            seen: set[str] = set()
            for entity in story.entities:
                name = entity.get("name", "")
                if name and name not in seen:
                    entity_counts[name] = entity_counts.get(name, 0) + 1
                    seen.add(name)

        sorted_themes = sorted(theme_counts.items(), key=lambda x: -x[1])
        sorted_entities = sorted(entity_counts.items(), key=lambda x: -x[1])

        top_themes = [{"name": n, "count": c} for n, c in sorted_themes[:_TOP_N]]
        top_entities = [{"name": n, "count": c} for n, c in sorted_entities[:_TOP_N]]

        return DashboardData(
            total_stories=total_in_range,
            top_themes=top_themes,
            top_entities=top_entities,
            recent_story_ids=[s.id for s in stories[:5]],
            distinct_theme_count=len(theme_counts),
            distinct_entity_count=len(entity_counts),
            sample_capped=sample_capped,
        )
