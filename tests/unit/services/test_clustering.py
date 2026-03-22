"""Tests for ClusteringService — cluster stories by signifier space proximity."""

import pytest

from src.domain.models import Story, StorySignification, TriadCoordinates, TriadResponseItem
from src.ports.errors import GraphError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


def make_story(story_id: str, x: float, y: float, triad_id: str = "workflow_nature") -> Story:
    return Story(
        id=story_id,
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        signification=StorySignification(responses=[
            TriadResponseItem(kind="triad", signifier_id=triad_id, coordinates=TriadCoordinates(x=x, y=y)),
            TriadResponseItem(kind="triad", signifier_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadResponseItem(kind="triad", signifier_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ]),
        processing_status="processed",
        entities=[{"name": "CI pipeline", "type": "tool"}],
        themes=["automation friction"],
    )


class FakeGraph(GraphPort):
    def __init__(self, communities: list[tuple[str, int]] | None = None):
        self._communities = communities or []

    def save_story_node(self, story_id, triads, timestamp): pass
    def save_entity_nodes(self, story_id, entities): pass
    def save_theme_nodes(self, story_id, themes): pass
    def save_proximity_relationships(self, story_id, pairs): pass
    def find_story_ids_by_entity(self, entity_name, limit, offset, from_date=None, to_date=None): return []
    def count_stories_by_entity(self, entity_name): return 0
    def find_themes_ranked(self, limit, from_date=None, to_date=None): return []
    def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None): return []
    def count_stories_by_theme(self, theme_name): return 0
    def find_entity_correlations(self, limit, threshold=0.0, entity_type=None): return []
    def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0): return []
    def find_theme_counts_by_window(self, window_size, from_date=None, to_date=None, theme=None): return []
    def find_entity_counts_by_window(self, window_size, from_date=None, to_date=None, entity=None): return []
    def find_story_communities(self, triad_id): return self._communities


class FakeStorage(StoragePort):
    def __init__(self, stories: dict | None = None):
        self._stories = stories or {}

    def save_story(self, story: Story) -> str: return story.id
    def get_story(self, story_id: str) -> Story: return self._stories[story_id]
    def count_stories(self, from_date=None, to_date=None) -> int: return len(self._stories)
    def list_stories(self, limit=20, offset=0, from_date=None, to_date=None) -> list:
        return list(self._stories.values())[offset:offset + limit]
    def update_story_entities(self, story_id, entities, themes, entity_status): pass
    def update_story_sentiment(self, story_id, sentiment, sentiment_status): pass
    def find_story_ids_requiring_processing(self): return []


class FailingGraph(FakeGraph):
    def find_story_communities(self, triad_id):
        raise GraphError("GDS unavailable")


# ── Test 1: groups stories into clusters by community ID ──────────────────────


def test_clustering_groups_stories_by_community_id():
    """cluster_by_triad groups stories with the same community_id into one cluster."""
    from src.services.clustering import ClusteringService

    s1 = make_story("s1", 0.1, 0.1)
    s2 = make_story("s2", 0.15, 0.12)
    s3 = make_story("s3", 0.9, 0.85)

    graph = FakeGraph(communities=[("s1", 0), ("s2", 0), ("s3", 1)])
    storage = FakeStorage(stories={"s1": s1, "s2": s2, "s3": s3})

    service = ClusteringService(graph=graph, storage=storage)
    result = service.cluster_by_triad("workflow_nature")

    assert len(result.clusters) == 2
    sizes = sorted(len(c.story_ids) for c in result.clusters)
    assert sizes == [1, 2]


# ── Test 2: computes centroid per cluster ─────────────────────────────────────


def test_clustering_computes_centroid():
    """cluster_by_triad computes mean x and mean y of member coordinates."""
    from src.services.clustering import ClusteringService

    s1 = make_story("s1", 0.2, 0.4)
    s2 = make_story("s2", 0.4, 0.6)

    graph = FakeGraph(communities=[("s1", 0), ("s2", 0)])
    storage = FakeStorage(stories={"s1": s1, "s2": s2})

    service = ClusteringService(graph=graph, storage=storage)
    result = service.cluster_by_triad("workflow_nature")

    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    assert abs(cluster.center_x - 0.3) < 1e-9
    assert abs(cluster.center_y - 0.5) < 1e-9


# ── Test 3: aggregates top themes per cluster ─────────────────────────────────


def test_clustering_aggregates_themes():
    """cluster_by_triad collects and deduplicates themes across cluster members."""
    from src.services.clustering import ClusteringService

    s1 = make_story("s1", 0.1, 0.1)
    s1.themes = ["automation friction", "tooling"]
    s2 = make_story("s2", 0.12, 0.11)
    s2.themes = ["automation friction", "ci"]

    graph = FakeGraph(communities=[("s1", 0), ("s2", 0)])
    storage = FakeStorage(stories={"s1": s1, "s2": s2})

    service = ClusteringService(graph=graph, storage=storage)
    result = service.cluster_by_triad("workflow_nature")

    themes = result.clusters[0].top_themes
    assert "automation friction" in themes


# ── Test 4: aggregates top entities per cluster ───────────────────────────────


def test_clustering_aggregates_entities():
    """cluster_by_triad collects and ranks entity names across cluster members."""
    from src.services.clustering import ClusteringService

    s1 = make_story("s1", 0.1, 0.1)
    s1.entities = [{"name": "CI pipeline", "type": "tool"}, {"name": "deployment", "type": "process"}]
    s2 = make_story("s2", 0.12, 0.11)
    s2.entities = [{"name": "CI pipeline", "type": "tool"}]

    graph = FakeGraph(communities=[("s1", 0), ("s2", 0)])
    storage = FakeStorage(stories={"s1": s1, "s2": s2})

    service = ClusteringService(graph=graph, storage=storage)
    result = service.cluster_by_triad("workflow_nature")

    entities = result.clusters[0].top_entities
    assert "CI pipeline" in entities
    # CI pipeline appears twice so should rank first
    assert entities[0] == "CI pipeline"


# ── Test 5: returns empty list when no communities ────────────────────────────


def test_clustering_returns_empty_when_no_communities():
    """cluster_by_triad returns empty cluster list when graph has no proximity data."""
    from src.services.clustering import ClusteringService

    graph = FakeGraph(communities=[])
    service = ClusteringService(graph=graph, storage=FakeStorage())
    result = service.cluster_by_triad("workflow_nature")

    assert result.clusters == []


# ── Test 6: ignores stories missing the requested triad placement ─────────────


def test_clustering_ignores_stories_without_triad_placement():
    """Stories whose community_id is present but have no matching triad are skipped for centroid."""
    from src.services.clustering import ClusteringService

    s1 = make_story("s1", 0.3, 0.5, triad_id="workflow_nature")
    s2 = make_story("s2", 0.1, 0.2, triad_id="other_triad")  # wrong triad

    graph = FakeGraph(communities=[("s1", 0), ("s2", 0)])
    storage = FakeStorage(stories={"s1": s1, "s2": s2})

    service = ClusteringService(graph=graph, storage=storage)
    result = service.cluster_by_triad("workflow_nature")

    assert len(result.clusters) == 1
    # Centroid should only be based on s1
    assert abs(result.clusters[0].center_x - 0.3) < 1e-9


# ── Test 7: GraphError propagates ────────────────────────────────────────────


def test_clustering_propagates_graph_error():
    """GraphError from find_story_communities propagates to the caller."""
    from src.services.clustering import ClusteringService

    service = ClusteringService(graph=FailingGraph(), storage=FakeStorage())
    with pytest.raises(GraphError):
        service.cluster_by_triad("workflow_nature")
