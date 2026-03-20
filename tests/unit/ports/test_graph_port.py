"""Tests for GraphPort interface."""

import pytest


def test_graph_port_is_abstract():
    """GraphPort cannot be instantiated directly."""
    from src.ports.graph import GraphPort

    with pytest.raises(TypeError, match="abstract"):
        GraphPort()


def test_can_implement_graph_port():
    """Can create a valid GraphPort implementation."""
    from src.domain.models import TriadCoordinates, TriadPlacement
    from src.ports.graph import GraphPort

    class FakeGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            pass

        def save_entity_nodes(self, story_id: str, entities: list) -> None:
            pass

        def save_theme_nodes(self, story_id: str, themes: list) -> None:
            pass

        def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
            pass

        def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int) -> list:
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

        def find_story_communities(self, triad_id):
            return []


    graph = FakeGraph()
    assert graph is not None
    assert isinstance(graph, GraphPort)

    # Should be able to call the method
    graph.save_story_node(
        "test-id",
        [TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5))],
        "2024-11-28T12:00:00Z",
    )
