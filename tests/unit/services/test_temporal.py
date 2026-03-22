"""Tests for TemporalService — time-windowed pattern analysis."""

from datetime import datetime, UTC

import pytest

from src.domain.models import Story, TriadCoordinates, TriadPlacement
from src.ports.errors import GraphError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


from src.domain.models import StoryMetadata


def make_story(
    story_id: str,
    timestamp: datetime,
    x: float = 0.3,
    y: float = 0.5,
    department: str | None = None,
    role: str | None = None,
) -> Story:
    metadata = StoryMetadata(department=department, role=role) if (department or role) else None
    return Story(
        id=story_id,
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=x, y=y)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status="processed",
        timestamp=timestamp,
        themes=["automation friction"],
        entities=[{"name": "CI pipeline", "type": "tool"}],
        metadata=metadata,
    )


class FakeGraph(GraphPort):
    def __init__(
        self,
        theme_windows: list[tuple[str, str, int]] | None = None,
        entity_windows: list[tuple[str, str, int]] | None = None,
        entity_ids: list[str] | None = None,
        theme_ids: list[str] | None = None,
    ):
        self._theme_windows = theme_windows or []
        self._entity_windows = entity_windows or []
        self._entity_ids = entity_ids or []
        self._theme_ids = theme_ids or []
        self.theme_window_calls: list[dict] = []
        self.entity_window_calls: list[dict] = []

    def save_story_node(self, story_id, triads, timestamp): pass
    def save_entity_nodes(self, story_id, entities): pass
    def save_theme_nodes(self, story_id, themes): pass
    def save_proximity_relationships(self, story_id, pairs): pass
    def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
        return self._entity_ids[offset:offset + limit]
    def count_stories_by_entity(self, entity_name): return len(self._entity_ids)
    def find_themes_ranked(self, limit, from_date=None, to_date=None): return []
    def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
        return self._theme_ids[offset:offset + limit]
    def count_stories_by_theme(self, theme_name): return len(self._theme_ids)
    def find_entity_correlations(self, limit, threshold=0.0, entity_type=None): return []
    def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0): return []
    def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None):
        self.theme_window_calls.append({"window_size": window_size, "theme": theme})
        return self._theme_windows
    def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None):
        self.entity_window_calls.append({"window_size": window_size, "entity": entity})
        return self._entity_windows
    def find_story_communities(self, triad_id): return []


class FakeStorage(StoragePort):
    def __init__(self, stories: dict | None = None):
        self._stories = stories or {}

    def save_story(self, story): return story.id
    def get_story(self, story_id): return self._stories[story_id]
    def count_stories(self, from_date=None, to_date=None): return len(self._stories)
    def list_stories(self, limit=20, offset=0, from_date=None, to_date=None):
        return list(self._stories.values())[offset:offset + limit]
    def update_story_entities(self, story_id, entities, themes, processing_status): pass
    def update_story_sentiment(self, story_id, sentiment, processing_status): pass


class FailingGraph(FakeGraph):
    def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None):
        raise GraphError("graph down")


# ── Test 1: theme timelines grouped correctly ─────────────────────────────────


def test_temporal_groups_theme_timelines():
    """query_temporal groups raw (window, theme, count) rows into ThemeTimeline objects."""
    from src.services.temporal import TemporalService

    graph = FakeGraph(
        theme_windows=[
            ("2026-01", "automation friction", 3),
            ("2026-02", "automation friction", 1),
            ("2026-01", "ci issues", 2),
        ],
        entity_windows=[],
    )
    service = TemporalService(graph=graph, storage=FakeStorage())
    result = service.query_temporal(from_date=None, to_date=None)

    names = [t.theme for t in result.theme_frequency]
    assert "automation friction" in names
    af = next(t for t in result.theme_frequency if t.theme == "automation friction")
    windows = {w.window: w.count for w in af.windows}
    assert windows["2026-01"] == 3
    assert windows["2026-02"] == 1


# ── Test 2: entity timelines grouped correctly ────────────────────────────────


def test_temporal_groups_entity_timelines():
    """query_temporal groups raw (window, entity, count) rows into EntityTimeline objects."""
    from src.services.temporal import TemporalService

    graph = FakeGraph(
        theme_windows=[],
        entity_windows=[
            ("2026-01", "CI pipeline", 2),
            ("2026-02", "CI pipeline", 4),
        ],
    )
    service = TemporalService(graph=graph, storage=FakeStorage())
    result = service.query_temporal(from_date=None, to_date=None)

    assert len(result.entity_frequency) == 1
    ef = result.entity_frequency[0]
    assert ef.entity == "CI pipeline"
    counts = {w.window: w.count for w in ef.windows}
    assert counts["2026-01"] == 2
    assert counts["2026-02"] == 4


# ── Test 3: windows list is union of all observed windows ─────────────────────


def test_temporal_windows_is_sorted_union():
    """result.windows contains all unique window labels across themes and entities, sorted."""
    from src.services.temporal import TemporalService

    graph = FakeGraph(
        theme_windows=[("2026-01", "x", 1), ("2026-03", "x", 2)],
        entity_windows=[("2026-02", "y", 1)],
    )
    service = TemporalService(graph=graph, storage=FakeStorage())
    result = service.query_temporal(from_date=None, to_date=None)

    assert result.windows == ["2026-01", "2026-02", "2026-03"]


# ── Test 4: bounded from/to fills gap windows ─────────────────────────────────


def test_temporal_generates_full_window_sequence_when_bounded():
    """When both from_date and to_date are given, all month windows are included even if empty."""
    from src.services.temporal import TemporalService

    # Only January data, but range covers Jan–Mar
    graph = FakeGraph(
        theme_windows=[("2026-01", "x", 1)],
        entity_windows=[],
    )
    service = TemporalService(graph=graph, storage=FakeStorage())
    result = service.query_temporal(
        from_date="2026-01-01T00:00:00",
        to_date="2026-03-31T23:59:59",
    )

    assert "2026-01" in result.windows
    assert "2026-02" in result.windows
    assert "2026-03" in result.windows


# ── Test 5: triad drift computed from storage ─────────────────────────────────


def test_temporal_computes_triad_drift():
    """triad_drift contains centroid per window per triad_id from story coordinates."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    feb = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    s1 = make_story("s1", jan, x=0.2, y=0.4)
    s2 = make_story("s2", feb, x=0.6, y=0.8)

    storage = FakeStorage(stories={"s1": s1, "s2": s2})
    service = TemporalService(graph=FakeGraph(), storage=storage)
    result = service.query_temporal(from_date=None, to_date=None)

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    by_window = {c.window: c for c in drift.centroids}
    assert abs(by_window["2026-01"].center_x - 0.2) < 1e-9
    assert abs(by_window["2026-02"].center_x - 0.6) < 1e-9


# ── Test 6: theme filter passed through to graph ─────────────────────────────


def test_temporal_passes_theme_filter_to_graph():
    """query_temporal forwards theme filter to find_theme_counts_by_window."""
    from src.services.temporal import TemporalService

    graph = FakeGraph()
    service = TemporalService(graph=graph, storage=FakeStorage())
    service.query_temporal(from_date=None, to_date=None, theme="automation friction")

    assert len(graph.theme_window_calls) == 1
    assert graph.theme_window_calls[0]["theme"] == "automation friction"


# ── Test 7: entity filter passed through to graph ────────────────────────────


def test_temporal_passes_entity_filter_to_graph():
    """query_temporal forwards entity filter to find_entity_counts_by_window."""
    from src.services.temporal import TemporalService

    graph = FakeGraph()
    service = TemporalService(graph=graph, storage=FakeStorage())
    service.query_temporal(from_date=None, to_date=None, entity="CI pipeline")

    assert len(graph.entity_window_calls) == 1
    assert graph.entity_window_calls[0]["entity"] == "CI pipeline"


# ── Test 8: theme filter restricts drift to matching story IDs ────────────────


def test_temporal_theme_filter_restricts_drift():
    """When theme filter is given, drift is computed only from matching story IDs."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    feb = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    s1 = make_story("s1", jan, x=0.1, y=0.1)  # matches theme
    s2 = make_story("s2", feb, x=0.9, y=0.9)  # does NOT match theme

    # graph returns only s1 for the theme query
    graph = FakeGraph(theme_ids=["s1"])
    storage = FakeStorage(stories={"s1": s1, "s2": s2})
    service = TemporalService(graph=graph, storage=storage)
    result = service.query_temporal(from_date=None, to_date=None, theme="automation friction")

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    # Only s1 should contribute — s2 excluded
    assert all(c.story_count == 1 for c in drift.centroids)
    by_window = {c.window: c for c in drift.centroids}
    assert "2026-01" in by_window
    assert "2026-02" not in by_window


# ── Test 9: GraphError propagates ─────────────────────────────────────────────


def test_temporal_propagates_graph_error():
    """GraphError from find_theme_counts_by_window propagates to caller."""
    from src.services.temporal import TemporalService

    service = TemporalService(graph=FailingGraph(), storage=FakeStorage())
    with pytest.raises(GraphError):
        service.query_temporal(from_date=None, to_date=None)


# ── Test 10: combined theme+entity filters intersect for drift ────────────────


def test_temporal_combined_filters_intersect_drift():
    """When both theme and entity are given, drift uses only stories matching both."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    feb = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    # s1 matches theme only, s2 matches entity only, s3 matches both
    s1 = make_story("s1", jan, x=0.1, y=0.1)
    s2 = make_story("s2", feb, x=0.5, y=0.5)
    s3 = make_story("s3", jan, x=0.9, y=0.9)

    # theme filter returns s1 + s3, entity filter returns s2 + s3 → intersection is s3
    graph = FakeGraph(theme_ids=["s1", "s3"], entity_ids=["s2", "s3"])
    storage = FakeStorage(stories={"s1": s1, "s2": s2, "s3": s3})
    service = TemporalService(graph=graph, storage=storage)
    result = service.query_temporal(
        from_date=None, to_date=None,
        theme="automation friction", entity="CI pipeline",
    )

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    # Only s3 contributes — single centroid in Jan at (0.9, 0.9)
    assert len(drift.centroids) == 1
    assert drift.centroids[0].window == "2026-01"
    assert abs(drift.centroids[0].center_x - 0.9) < 1e-9


# ── Test 11: department filter restricts drift ────────────────────────────────


def test_temporal_department_filter_restricts_drift():
    """department filter limits drift to stories with matching department metadata."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    feb = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    s1 = make_story("s1", jan, x=0.1, y=0.1, department="engineering")
    s2 = make_story("s2", feb, x=0.9, y=0.9, department="product")

    storage = FakeStorage(stories={"s1": s1, "s2": s2})
    service = TemporalService(graph=FakeGraph(), storage=storage)
    result = service.query_temporal(from_date=None, to_date=None, department="engineering")

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    # Only s1 (engineering) contributes
    assert len(drift.centroids) == 1
    assert drift.centroids[0].window == "2026-01"
    assert abs(drift.centroids[0].center_x - 0.1) < 1e-9


# ── Test 12: role filter restricts drift ──────────────────────────────────────


def test_temporal_role_filter_restricts_drift():
    """role filter limits drift to stories with matching role metadata."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    feb = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    s1 = make_story("s1", jan, x=0.2, y=0.2, role="developer")
    s2 = make_story("s2", feb, x=0.8, y=0.8, role="manager")

    storage = FakeStorage(stories={"s1": s1, "s2": s2})
    service = TemporalService(graph=FakeGraph(), storage=storage)
    result = service.query_temporal(from_date=None, to_date=None, role="developer")

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    assert len(drift.centroids) == 1
    assert drift.centroids[0].window == "2026-01"
    assert abs(drift.centroids[0].center_x - 0.2) < 1e-9


# ── Test 13: department + role both required ──────────────────────────────────


def test_temporal_department_and_role_both_required():
    """When both department and role given, story must match both."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    # s1: engineering + developer (matches both)
    # s2: engineering + manager (matches department only)
    # s3: product + developer (matches role only)
    s1 = make_story("s1", jan, x=0.1, y=0.1, department="engineering", role="developer")
    s2 = make_story("s2", jan, x=0.5, y=0.5, department="engineering", role="manager")
    s3 = make_story("s3", jan, x=0.9, y=0.9, department="product", role="developer")

    storage = FakeStorage(stories={"s1": s1, "s2": s2, "s3": s3})
    service = TemporalService(graph=FakeGraph(), storage=storage)
    result = service.query_temporal(
        from_date=None, to_date=None, department="engineering", role="developer"
    )

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    # Only s1 matches both
    assert len(drift.centroids) == 1
    assert abs(drift.centroids[0].center_x - 0.1) < 1e-9


# ── Test 14: stories without metadata excluded by department filter ────────────


def test_temporal_no_metadata_excluded_by_department_filter():
    """Stories with no metadata are excluded when a department filter is active."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    s1 = make_story("s1", jan, x=0.3, y=0.3, department="engineering")
    s2 = make_story("s2", jan, x=0.7, y=0.7)  # no metadata

    storage = FakeStorage(stories={"s1": s1, "s2": s2})
    service = TemporalService(graph=FakeGraph(), storage=storage)
    result = service.query_temporal(from_date=None, to_date=None, department="engineering")

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    # s2 has no metadata, must be excluded
    assert len(drift.centroids) == 1
    assert abs(drift.centroids[0].center_x - 0.3) < 1e-9


# ── Test 15: department + theme filter intersects both ────────────────────────


def test_temporal_department_and_theme_intersect():
    """department filter and theme filter both restrict drift; story must match both."""
    from src.services.temporal import TemporalService

    jan = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    feb = datetime(2026, 2, 10, 10, 0, tzinfo=UTC)
    # s1: engineering, matches theme → should appear in drift
    # s2: product, matches theme → excluded by department
    # s3: engineering, not in theme IDs → excluded by theme
    s1 = make_story("s1", jan, x=0.1, y=0.1, department="engineering")
    s2 = make_story("s2", feb, x=0.5, y=0.5, department="product")
    s3 = make_story("s3", jan, x=0.9, y=0.9, department="engineering")

    # theme filter returns s1 + s2 from the graph
    graph = FakeGraph(theme_ids=["s1", "s2"])
    storage = FakeStorage(stories={"s1": s1, "s2": s2, "s3": s3})
    service = TemporalService(graph=graph, storage=storage)
    result = service.query_temporal(
        from_date=None, to_date=None,
        theme="automation friction", department="engineering",
    )

    drift = next((d for d in result.triad_drift if d.triad_id == "workflow_nature"), None)
    assert drift is not None
    # Only s1 matches theme AND engineering department
    assert len(drift.centroids) == 1
    assert drift.centroids[0].window == "2026-01"
    assert abs(drift.centroids[0].center_x - 0.1) < 1e-9
