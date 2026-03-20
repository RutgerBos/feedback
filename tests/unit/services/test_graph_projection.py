"""Tests for GraphProjectionService."""

import pytest

from src.domain.models import Story, TriadCoordinates, TriadPlacement
from src.ports.errors import GraphError, NotFoundError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


def make_story(story_id: str = "story-1", processing_status: str = "processed") -> Story:
    story = Story(
        id=story_id,
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
        processing_status=processing_status,
        entities=[{"name": "CI pipeline", "type": "tool"}, {"name": "deployment", "type": "process"}],
    )
    return story


class FakeStorage(StoragePort):
    def __init__(self, stories: dict = None):
        self.stories = stories or {}

    def save_story(self, story: Story) -> str:
        self.stories[story.id] = story
        return story.id

    def get_story(self, story_id: str) -> Story:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        return self.stories[story_id]

    def count_stories(self, from_date=None, to_date=None) -> int:
        return len(self.stories)

    def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list:
        return list(self.stories.values())[offset:offset + limit]

    def update_story_entities(self, story_id: str, entities: list, themes: list, processing_status: str) -> None:
        pass

    def update_story_sentiment(self, story_id: str, sentiment, processing_status: str) -> None:
        pass


class FakeGraph(GraphPort):
    def __init__(self):
        self.saved_entity_calls = []  # list of (story_id, entities)
        self.saved_theme_calls = []   # list of (story_id, themes)

    def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
        pass

    def save_entity_nodes(self, story_id: str, entities: list) -> None:
        self.saved_entity_calls.append((story_id, entities))

    def save_theme_nodes(self, story_id: str, themes: list) -> None:
        self.saved_theme_calls.append((story_id, themes))

    def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
        pass

    def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int, from_date=None, to_date=None) -> list:
        return []

    def count_stories_by_entity(self, entity_name: str) -> int:
        return 0

    def find_themes_ranked(self, limit, from_date=None, to_date=None):
        return []

    def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
        return []

    def count_stories_by_theme(self, theme_name):
        return 0
    def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
        return []

    def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
        return []
    def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
    def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

    def find_story_communities(self, triad_id):
        return []



class FailingGraph(GraphPort):
    def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
        pass

    def save_entity_nodes(self, story_id: str, entities: list) -> None:
        raise GraphError("Neo4j unavailable")

    def save_theme_nodes(self, story_id: str, themes: list) -> None:
        raise GraphError("Neo4j unavailable")

    def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
        raise GraphError("Neo4j unavailable")

    def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int, from_date=None, to_date=None) -> list:
        return []

    def count_stories_by_entity(self, entity_name: str) -> int:
        return 0

    def find_themes_ranked(self, limit, from_date=None, to_date=None):
        return []

    def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
        return []

    def count_stories_by_theme(self, theme_name):
        return 0
    def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
        return []

    def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
        return []
    def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
    def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

    def find_story_communities(self, triad_id):
        return []



# ── Test 1: can instantiate ────────────────────────────────────────────────────

def test_graph_projection_service_can_be_created():
    """GraphProjectionService accepts storage and graph dependencies."""
    from src.services.graph_projection import GraphProjectionService

    service = GraphProjectionService(storage=FakeStorage(), graph=FakeGraph())
    assert service is not None


# ── Test 2: projects entities for a processed story ───────────────────────────

def test_save_entities_for_story_calls_save_entity_nodes():
    """save_entities_for_story reads story and calls graph.save_entity_nodes()."""
    from src.services.graph_projection import GraphProjectionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    graph = FakeGraph()

    service = GraphProjectionService(storage=storage, graph=graph)
    service.save_entities_for_story(story.id)

    assert len(graph.saved_entity_calls) == 1
    called_story_id, called_entities = graph.saved_entity_calls[0]
    assert called_story_id == story.id
    assert called_entities == story.entities


# ── Test 3: skips projection when story is not processed ──────────────────────

def test_save_entities_for_story_skips_unprocessed_stories():
    """save_entities_for_story does nothing if processing_status != 'processed'."""
    from src.services.graph_projection import GraphProjectionService

    for status in ("pending", "failed"):
        story = make_story(processing_status=status)
        storage = FakeStorage(stories={story.id: story})
        graph = FakeGraph()

        service = GraphProjectionService(storage=storage, graph=graph)
        service.save_entities_for_story(story.id)

        assert graph.saved_entity_calls == [], f"Expected no calls for status={status!r}"


# ── Test 4: handles GraphError gracefully ─────────────────────────────────────

def test_save_entities_for_story_handles_graph_error_gracefully():
    """GraphError from the graph adapter is caught and does not propagate."""
    from src.services.graph_projection import GraphProjectionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})

    service = GraphProjectionService(storage=storage, graph=FailingGraph())

    service.save_entities_for_story(story.id)  # must not raise


# ── Test 5: propagates NotFoundError ──────────────────────────────────────────

def test_save_entities_for_story_propagates_not_found():
    """NotFoundError propagates when the story does not exist."""
    from src.services.graph_projection import GraphProjectionService

    service = GraphProjectionService(storage=FakeStorage(), graph=FakeGraph())

    with pytest.raises(NotFoundError):
        service.save_entities_for_story("nonexistent-id")


# ── Tests for save_themes_for_story ───────────────────────────────────────────

def test_save_themes_for_story_calls_save_theme_nodes():
    """save_themes_for_story reads story and calls graph.save_theme_nodes()."""
    from src.services.graph_projection import GraphProjectionService

    story = make_story()
    story.themes = ["automation friction", "developer experience"]
    storage = FakeStorage(stories={story.id: story})
    graph = FakeGraph()

    service = GraphProjectionService(storage=storage, graph=graph)
    service.save_themes_for_story(story.id)

    assert len(graph.saved_theme_calls) == 1
    called_story_id, called_themes = graph.saved_theme_calls[0]
    assert called_story_id == story.id
    assert called_themes == story.themes


def test_save_themes_for_story_skips_unprocessed_stories():
    """save_themes_for_story does nothing if processing_status != 'processed'."""
    from src.services.graph_projection import GraphProjectionService

    for status in ("pending", "failed"):
        story = make_story(processing_status=status)
        story.themes = ["some theme"]
        storage = FakeStorage(stories={story.id: story})
        graph = FakeGraph()

        service = GraphProjectionService(storage=storage, graph=graph)
        service.save_themes_for_story(story.id)

        assert graph.saved_theme_calls == [], f"Expected no calls for status={status!r}"


def test_save_themes_for_story_handles_graph_error_gracefully():
    """GraphError from the graph adapter is caught and does not propagate."""
    from src.services.graph_projection import GraphProjectionService

    story = make_story()
    story.themes = ["automation"]
    storage = FakeStorage(stories={story.id: story})

    service = GraphProjectionService(storage=storage, graph=FailingGraph())

    service.save_themes_for_story(story.id)  # must not raise


# ── Tests for project_story ───────────────────────────────────────────────────

def test_project_story_calls_both_entity_and_theme_projection():
    """project_story delegates to both save_entities_for_story and save_themes_for_story."""
    from src.services.graph_projection import GraphProjectionService

    story = make_story()
    story.themes = ["automation friction"]
    storage = FakeStorage(stories={story.id: story})
    graph = FakeGraph()

    service = GraphProjectionService(storage=storage, graph=graph)
    service.project_story(story.id)

    assert len(graph.saved_entity_calls) == 1
    assert len(graph.saved_theme_calls) == 1


def test_project_story_continues_themes_after_entity_graph_error():
    """A GraphError in entity projection does not block theme projection."""
    from src.services.graph_projection import GraphProjectionService

    class EntityFailingGraph(GraphPort):
        def __init__(self):
            self.saved_theme_calls = []

        def save_story_node(self, story_id, triads, timestamp):
            pass

        def save_entity_nodes(self, story_id, entities):
            raise GraphError("entity failure")

        def save_theme_nodes(self, story_id, themes):
            self.saved_theme_calls.append((story_id, themes))

        def save_proximity_relationships(self, story_id, pairs):
            pass

        def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None):
            return []

        def count_stories_by_entity(self, entity_name):
            return 0

        def find_themes_ranked(self, limit, from_date=None, to_date=None):
            return []

        def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
            return []

        def count_stories_by_theme(self, theme_name):
            return 0

        def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
            return []

        def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
            return []
        def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
        def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []

        def find_story_communities(self, triad_id):
            return []

    story = make_story()
    story.themes = ["some theme"]
    storage = FakeStorage(stories={story.id: story})
    graph = EntityFailingGraph()

    service = GraphProjectionService(storage=storage, graph=graph)
    service.project_story(story.id)  # must not raise

    # Theme projection ran despite entity failure
    assert len(graph.saved_theme_calls) == 1


# ── Story 3.4: proximity wiring ───────────────────────────────────────────────

def test_project_story_calls_proximity_calculation():
    """project_story calls proximity calculation after entity and theme projection."""
    from src.services.graph_projection import GraphProjectionService

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    graph = FakeGraph()

    proximity_calls = []

    class TrackingProximity:
        def calculate_for_story(self, story_id: str) -> None:
            proximity_calls.append(story_id)

    service = GraphProjectionService(
        storage=storage,
        graph=graph,
        proximity=TrackingProximity(),
    )
    service.project_story(story.id)

    assert proximity_calls == [story.id]


def test_project_story_swallows_proximity_graph_error():
    """A GraphError from proximity calculation does not propagate."""
    from src.services.graph_projection import GraphProjectionService

    class FailingProximity:
        def calculate_for_story(self, story_id: str) -> None:
            raise GraphError("proximity failure")

    story = make_story()
    storage = FakeStorage(stories={story.id: story})
    graph = FakeGraph()

    service = GraphProjectionService(
        storage=storage,
        graph=graph,
        proximity=FailingProximity(),
    )
    service.project_story(story.id)  # must not raise
