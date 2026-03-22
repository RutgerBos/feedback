"""
TemporalService: time-windowed pattern analysis over themes, entities, and triad coordinates.
"""

from dataclasses import dataclass, field
from datetime import datetime, UTC

from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


@dataclass
class WindowedCount:
    """
    Responsibilities:
    - Hold a count for one time window

    Collaborators:
    - None (value object)
    """

    window: str
    count: int


@dataclass
class ThemeTimeline:
    """
    Responsibilities:
    - Hold per-window story counts for one theme

    Collaborators:
    - WindowedCount (value object)
    """

    theme: str
    windows: list[WindowedCount]


@dataclass
class EntityTimeline:
    """
    Responsibilities:
    - Hold per-window story counts for one entity

    Collaborators:
    - WindowedCount (value object)
    """

    entity: str
    windows: list[WindowedCount]


@dataclass
class WindowedCentroid:
    """
    Responsibilities:
    - Hold the mean triad coordinate and story count for one time window

    Collaborators:
    - None (value object)
    """

    window: str
    center_x: float
    center_y: float
    story_count: int


@dataclass
class TriadDrift:
    """
    Responsibilities:
    - Hold centroid movement over time for one triad

    Collaborators:
    - WindowedCentroid (value object)
    """

    triad_id: str
    centroids: list[WindowedCentroid]


@dataclass
class TemporalResult:
    """
    Responsibilities:
    - Hold all temporal analysis results for one query

    Collaborators:
    - ThemeTimeline, EntityTimeline, TriadDrift (value objects)
    """

    windows: list[str] = field(default_factory=list)
    theme_frequency: list[ThemeTimeline] = field(default_factory=list)
    entity_frequency: list[EntityTimeline] = field(default_factory=list)
    triad_drift: list[TriadDrift] = field(default_factory=list)


def _window_len(window_size: str) -> int:
    return 7 if window_size == "month" else 10


def _generate_month_windows(from_label: str, to_label: str) -> list[str]:
    """Generate YYYY-MM labels from from_label to to_label inclusive."""
    year, month = int(from_label[:4]), int(from_label[5:7])
    end_year, end_month = int(to_label[:4]), int(to_label[5:7])
    windows = []
    while (year, month) <= (end_year, end_month):
        windows.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return windows


def _generate_day_windows(from_label: str, to_label: str) -> list[str]:
    """Generate YYYY-MM-DD labels from from_label to to_label inclusive."""
    from datetime import date, timedelta
    start = date.fromisoformat(from_label)
    end = date.fromisoformat(to_label)
    windows = []
    current = start
    while current <= end:
        windows.append(current.isoformat())
        current += timedelta(days=1)
    return windows


def _parse_iso_to_naive_utc(iso: str) -> datetime:
    """Parse ISO8601 string to UTC-naive datetime for StoragePort."""
    normalized = iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _filter_by_metadata(stories, department: str | None, role: str | None):
    """Filter stories by metadata fields. Stories without metadata are excluded when a filter is set."""
    if department is None and role is None:
        return stories
    result = []
    for story in stories:
        meta = story.metadata
        if meta is None:
            continue
        if department is not None and meta.department != department:
            continue
        if role is not None and meta.role != role:
            continue
        result.append(story)
    return result


class TemporalService:
    """
    Responsibilities:
    - Query per-window theme/entity counts from graph
    - Compute triad coordinate drift from storage stories
    - Apply theme/entity filters consistently across all result components
    - Generate full window sequences for bounded queries

    Collaborators:
    - GraphPort (theme/entity windowed counts, filtered story ID lookups)
    - StoragePort (story coordinates for drift computation)

    Notes:
    - GraphError propagates to caller
    - StoragePort receives datetime objects (UTC-naive); ISO strings are parsed here
    - When both theme and entity filters are given, drift uses intersection of IDs
    - N+1 storage reads for filtered drift — acceptable for current dataset sizes
    """

    def __init__(self, graph: GraphPort, storage: StoragePort) -> None:
        self._graph = graph
        self._storage = storage

    def query_temporal(
        self,
        from_date: str | None,
        to_date: str | None,
        window_size: str = "month",
        theme: str | None = None,
        entity: str | None = None,
        department: str | None = None,
        role: str | None = None,
    ) -> TemporalResult:
        """
        Return time-windowed theme frequency, entity frequency, and triad drift.

        Args:
            from_date:   ISO8601 string lower bound (inclusive), or None
            to_date:     ISO8601 string upper bound (inclusive), or None
            window_size: "month" (YYYY-MM) or "day" (YYYY-MM-DD)
            theme:       If given: theme_frequency shows only this theme;
                         drift uses only stories that have this theme
            entity:      If given: entity_frequency shows only this entity;
                         drift uses only stories that mention this entity;
                         when combined with theme, drift uses intersection of
                         both ID sets (stories matching theme AND entity)
            department:  If given: drift uses only stories with this department
                         metadata (no effect on theme/entity frequency)
            role:        If given: drift uses only stories with this role
                         metadata (no effect on theme/entity frequency)

        Notes on filter semantics:
            Each filter dimension is independent in frequency data — theme
            restricts theme_frequency, entity restricts entity_frequency.
            Drift uses the intersection of all active filters.
            Metadata filters (department, role) apply to drift only — the graph
            does not store story metadata.

        Returns:
            TemporalResult with theme_frequency, entity_frequency, triad_drift,
            and a windows list (generated full sequence when bounded, otherwise
            the observed union)

        Raises:
            GraphError: If any graph query fails
        """
        wlen = _window_len(window_size)

        # ── Theme and entity frequency (from graph) ──────────────────────────
        theme_rows = self._graph.find_theme_counts_by_window(
            window_size, from_date=from_date, to_date=to_date, theme=theme
        )
        entity_rows = self._graph.find_entity_counts_by_window(
            window_size, from_date=from_date, to_date=to_date, entity=entity
        )

        # Group theme rows by theme name
        theme_map: dict[str, dict[str, int]] = {}
        for window_label, theme_name, count in theme_rows:
            theme_map.setdefault(theme_name, {})[window_label] = count

        # Group entity rows by entity name
        entity_map: dict[str, dict[str, int]] = {}
        for window_label, entity_name, count in entity_rows:
            entity_map.setdefault(entity_name, {})[window_label] = count

        # ── Triad drift (from storage, filtered by theme/entity/metadata) ──────
        stories = self._collect_stories_for_drift(from_date, to_date, theme, entity, department, role)

        drift_map: dict[str, dict[str, list[tuple[float, float]]]] = {}
        for s in stories:
            window_label = s.timestamp.strftime("%Y-%m" if window_size == "month" else "%Y-%m-%d")
            for p in s.triads:
                drift_map.setdefault(p.triad_id, {}).setdefault(window_label, []).append(
                    (p.coordinates.x, p.coordinates.y)
                )

        # ── Assemble windows list ────────────────────────────────────────────
        observed: set[str] = set()
        for w, _, _ in theme_rows:
            observed.add(w)
        for w, _, _ in entity_rows:
            observed.add(w)
        for triad_windows in drift_map.values():
            observed.update(triad_windows.keys())

        if from_date and to_date:
            from_label = from_date[:wlen]
            to_label = to_date[:wlen]
            if window_size == "month":
                all_windows = _generate_month_windows(from_label, to_label)
            else:
                all_windows = _generate_day_windows(from_label, to_label)
        else:
            all_windows = sorted(observed)

        # ── Build result objects ─────────────────────────────────────────────
        theme_frequency = [
            ThemeTimeline(
                theme=name,
                windows=[WindowedCount(window=w, count=counts[w]) for w in sorted(counts)],
            )
            for name, counts in sorted(theme_map.items())
        ]

        entity_frequency = [
            EntityTimeline(
                entity=name,
                windows=[WindowedCount(window=w, count=counts[w]) for w in sorted(counts)],
            )
            for name, counts in sorted(entity_map.items())
        ]

        triad_drift = [
            TriadDrift(
                triad_id=triad_id,
                centroids=[
                    WindowedCentroid(
                        window=w,
                        center_x=sum(x for x, _ in coords) / len(coords),
                        center_y=sum(y for _, y in coords) / len(coords),
                        story_count=len(coords),
                    )
                    for w, coords in sorted(windows.items())
                ],
            )
            for triad_id, windows in sorted(drift_map.items())
        ]

        return TemporalResult(
            windows=all_windows,
            theme_frequency=theme_frequency,
            entity_frequency=entity_frequency,
            triad_drift=triad_drift,
        )

    def _collect_stories_for_drift(
        self,
        from_date: str | None,
        to_date: str | None,
        theme: str | None,
        entity: str | None,
        department: str | None,
        role: str | None,
    ):
        """
        Collect stories for triad drift computation.

        When theme or entity filter is given, collects matching story IDs from
        the graph (paginated), intersects them, then loads each story individually.
        Otherwise paginates through storage.

        Metadata filters (department, role) are applied in memory after loading
        because the graph does not store story metadata.

        Notes:
        - N+1 storage reads for the theme/entity filtered case — acceptable for
          current dataset sizes
        """
        if theme is not None or entity is not None:
            # Filtered: collect IDs from graph, intersect, load individually
            ids: set[str] | None = None

            if theme is not None:
                theme_ids = set(
                    self._paginate_ids(
                        lambda limit, offset: self._graph.find_story_ids_by_theme(
                            theme, limit=limit, offset=offset,
                            from_date=from_date, to_date=to_date,
                        )
                    )
                )
                ids = theme_ids if ids is None else ids & theme_ids

            if entity is not None:
                entity_ids = set(
                    self._paginate_ids(
                        lambda limit, offset: self._graph.find_story_ids_by_entity(
                            entity, limit=limit, offset=offset,
                            from_date=from_date, to_date=to_date,
                        )
                    )
                )
                ids = entity_ids if ids is None else ids & entity_ids

            stories = [self._storage.get_story(sid) for sid in (ids or set())]
        else:
            # Unfiltered: paginate through storage
            dt_from = _parse_iso_to_naive_utc(from_date) if from_date else None
            dt_to = _parse_iso_to_naive_utc(to_date) if to_date else None
            stories = self._collect_stories_paginated(dt_from, dt_to)

        return _filter_by_metadata(stories, department, role)

    def _collect_stories_paginated(self, from_date, to_date, page_size: int = 100):
        """Paginate through storage and collect all stories in date range."""
        stories = []
        offset = 0
        while True:
            page = self._storage.list_stories(
                limit=page_size, offset=offset,
                from_date=from_date, to_date=to_date,
            )
            stories.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return stories

    @staticmethod
    def _paginate_ids(fetch_fn, page_size: int = 100) -> list:
        """Paginate fetch_fn(limit, offset) until exhausted. Returns list of IDs."""
        results = []
        offset = 0
        while True:
            page = fetch_fn(page_size, offset)
            results.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return results
