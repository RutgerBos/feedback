"""Tests for Neo4jGraphAdapter."""

import pytest
from src.ports.graph import GraphPort
from src.domain.models import TriadPlacement, TriadCoordinates


STORY_ID = "story-abc"
TIMESTAMP = "2026-03-13T10:00:00Z"
TRIADS = [
    TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
    TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
    TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
]


class FakeSession:
    """Records Cypher queries and parameters for inspection."""

    def __init__(self):
        self.queries = []  # list of (query, params)

    def run(self, query: str, **params) -> None:
        self.queries.append((query, params))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeDriver:
    """Injects a FakeSession for each session() call."""

    def __init__(self):
        self.session_instance = FakeSession()

    def session(self):
        return self.session_instance


# ── Test 1: implements GraphPort ───────────────────────────────────────────────

def test_neo4j_adapter_implements_graph_port():
    """Neo4jGraphAdapter is a valid GraphPort implementation."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    assert isinstance(adapter, GraphPort)


# ── Test 2: save_story_node creates Story node with id and timestamp ───────────

def test_save_story_node_creates_story_node():
    """save_story_node runs a Cypher query that creates/merges a Story node."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_story_node(story_id=STORY_ID, triads=TRIADS, timestamp=TIMESTAMP)

    assert len(driver.session_instance.queries) >= 1
    query, params = driver.session_instance.queries[0]
    assert "Story" in query
    assert params.get("story_id") == STORY_ID
    assert params.get("timestamp") == TIMESTAMP


# ── Test 3: triad placements stored as properties ─────────────────────────────

def test_save_story_node_stores_triad_placements():
    """save_story_node persists triad placement data on the node."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_story_node(story_id=STORY_ID, triads=TRIADS, timestamp=TIMESTAMP)

    query, params = driver.session_instance.queries[0]
    triads_param = params.get("triads")
    assert triads_param is not None
    assert len(triads_param) == 3
    triad_ids = [t["triad_id"] for t in triads_param]
    assert "workflow_nature" in triad_ids


# ── Test 4: raises GraphError on driver failure ───────────────────────────────

def test_save_story_node_raises_graph_error_on_failure():
    """save_story_node raises GraphError when the driver raises."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter
    from src.ports.errors import GraphError

    class FailingSession:
        def run(self, query: str, **params):
            raise Exception("Neo4j unavailable")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class FailingDriver:
        def session(self):
            return FailingSession()

    adapter = Neo4jGraphAdapter(driver=FailingDriver())

    with pytest.raises(GraphError):
        adapter.save_story_node(story_id=STORY_ID, triads=TRIADS, timestamp=TIMESTAMP)
