"""Tests for GraphPort interface."""

import pytest


def test_graph_port_is_abstract():
    """GraphPort cannot be instantiated directly."""
    from src.ports.graph import GraphPort

    with pytest.raises(TypeError, match="abstract"):
        GraphPort()


def test_can_implement_graph_port():
    """Can create a valid GraphPort implementation."""
    from src.ports.graph import GraphPort
    from src.domain.models import TriadPlacement, TriadCoordinates

    class FakeGraph(GraphPort):
        def save_story_node(self, story_id: str, triads, timestamp: str) -> None:
            pass

    graph = FakeGraph()
    assert graph is not None
    assert isinstance(graph, GraphPort)

    # Should be able to call the method
    graph.save_story_node(
        "test-id",
        [TriadPlacement(triad_id="t1", coordinates=TriadCoordinates(x=0.5, y=0.5))],
        "2024-11-28T12:00:00Z",
    )
