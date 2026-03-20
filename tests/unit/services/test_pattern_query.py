"""Tests for PatternQueryService — query stories by entity."""

import pytest

from src.domain.models import Story, TriadCoordinates, TriadPlacement
from src.ports.errors import GraphError, NotFoundError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


def make_story(story_id: str = "story-1") -> Story:
    return Story(
        id=story_id,
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status="processed",
    )


class FakeGraph(GraphPort):
    def __init__(self, story_ids: list[str] | None = None, total: int = 0):
        self._story_ids = story_ids or []
        self._total = total
        self.find_calls: list[tuple[str, int, int]] = []
        self.count_calls: list[str] = []

    def save_story_node(self, story_id, triads, timestamp):
        pass

    def save_entity_nodes(self, story_id, entities):
        pass

    def save_theme_nodes(self, story_id, themes):
        pass

    def save_proximity_relationships(self, story_id, pairs):
        pass

    def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int) -> list[str]:
        self.find_calls.append((entity_name, limit, offset))
        return self._story_ids

    def count_stories_by_entity(self, entity_name: str) -> int:
        self.count_calls.append(entity_name)
        return self._total


class FakeStorage(StoragePort):
    def __init__(self, stories: dict | None = None):
        self._stories = stories or {}

    def save_story(self, story: Story) -> str:
        return story.id

    def get_story(self, story_id: str) -> Story:
        if story_id not in self._stories:
            raise NotFoundError(f"Story not found: {story_id}")
        return self._stories[story_id]

    def count_stories(self, from_date=None, to_date=None) -> int:
        return len(self._stories)

    def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list:
        return list(self._stories.values())[offset : offset + limit]

    def update_story_entities(self, story_id, entities, themes, processing_status):
        pass

    def update_story_sentiment(self, story_id, sentiment, processing_status):
        pass


class FailingGraph(FakeGraph):
    def find_story_ids_by_entity(self, entity_name, limit, offset):
        raise GraphError("Neo4j down")

    def count_stories_by_entity(self, entity_name):
        raise GraphError("Neo4j down")


# ── Test 1: returns story objects for matching entity ─────────────────────────


def test_query_by_entity_returns_stories():
    """query_by_entity fetches IDs from graph, loads stories from storage."""
    from src.services.pattern_query import PatternQueryService

    story = make_story("s1")
    graph = FakeGraph(story_ids=["s1"], total=1)
    storage = FakeStorage(stories={"s1": story})

    service = PatternQueryService(graph=graph, storage=storage)
    result = service.query_by_entity("CI pipeline", limit=10, offset=0)

    assert result.stories == [story]
    assert result.total == 1


# ── Test 2: passes limit and offset to the graph ──────────────────────────────


def test_query_by_entity_passes_pagination_to_graph():
    """limit and offset are forwarded to the graph port."""
    from src.services.pattern_query import PatternQueryService

    graph = FakeGraph(story_ids=[], total=0)
    storage = FakeStorage()

    service = PatternQueryService(graph=graph, storage=storage)
    service.query_by_entity("entity", limit=5, offset=10)

    assert graph.find_calls == [("entity", 5, 10)]
    assert graph.count_calls == ["entity"]


# ── Test 3: empty result when no stories match ────────────────────────────────


def test_query_by_entity_empty_when_no_matches():
    """Returns empty list and zero total when no stories mention the entity."""
    from src.services.pattern_query import PatternQueryService

    graph = FakeGraph(story_ids=[], total=0)
    service = PatternQueryService(graph=graph, storage=FakeStorage())
    result = service.query_by_entity("unknown entity", limit=10, offset=0)

    assert result.stories == []
    assert result.total == 0


# ── Test 4: propagates GraphError ─────────────────────────────────────────────


def test_query_by_entity_propagates_graph_error():
    """GraphError from the graph port is not swallowed."""
    from src.services.pattern_query import PatternQueryService

    service = PatternQueryService(graph=FailingGraph(), storage=FakeStorage())
    with pytest.raises(GraphError):
        service.query_by_entity("entity", limit=10, offset=0)


# ── Test 5: multiple stories returned in order ────────────────────────────────


def test_query_by_entity_returns_multiple_stories_in_order():
    """Returns all matching stories in the order returned by the graph."""
    from src.services.pattern_query import PatternQueryService

    s1 = make_story("s1")
    s2 = make_story("s2")
    graph = FakeGraph(story_ids=["s1", "s2"], total=2)
    storage = FakeStorage(stories={"s1": s1, "s2": s2})

    service = PatternQueryService(graph=graph, storage=storage)
    result = service.query_by_entity("CI pipeline", limit=10, offset=0)

    assert result.stories == [s1, s2]
    assert result.total == 2


# ── Test 6: stale graph ID raises NotFoundError ───────────────────────────────


def test_query_by_entity_propagates_not_found_for_stale_graph_id():
    """NotFoundError propagates when a graph ID has no corresponding story in storage."""
    from src.services.pattern_query import PatternQueryService

    graph = FakeGraph(story_ids=["stale-id"], total=1)
    storage = FakeStorage(stories={})  # storage does not have the story

    service = PatternQueryService(graph=graph, storage=storage)
    with pytest.raises(NotFoundError):
        service.query_by_entity("entity", limit=10, offset=0)


# ── Test 7: total reflects full count, not page size ─────────────────────────


def test_query_by_entity_total_is_full_count_not_page_size():
    """total is the full match count even when offset reduces the returned stories."""
    from src.services.pattern_query import PatternQueryService

    s3 = make_story("s3")
    # Graph returns only s3 (page 2), but total count is 3
    graph = FakeGraph(story_ids=["s3"], total=3)
    storage = FakeStorage(stories={"s3": s3})

    service = PatternQueryService(graph=graph, storage=storage)
    result = service.query_by_entity("entity", limit=1, offset=2)

    assert len(result.stories) == 1
    assert result.total == 3
