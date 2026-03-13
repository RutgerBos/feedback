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


# ── Test 3: triads accepted by the method signature ───────────────────────────

def test_save_story_node_accepts_triad_placements():
    """save_story_node accepts triad placements without error.

    Triad coordinates are not stored as node properties in Story 3.1 because
    Neo4j cannot store lists of maps as a property. Triad data will be modelled
    as relationships/nodes in Story 3.4.
    """
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    # Must not raise even though triads are not stored on the node
    adapter.save_story_node(story_id=STORY_ID, triads=TRIADS, timestamp=TIMESTAMP)

    assert len(driver.session_instance.queries) == 1


# ── Tests for save_entity_nodes ───────────────────────────────────────────────

ENTITIES = [
    {"name": "CI pipeline", "type": "tool"},
    {"name": "deployment", "type": "process"},
]


def test_save_entity_nodes_creates_entity_nodes_and_relationships():
    """save_entity_nodes creates Entity nodes and MENTIONS relationships in one transaction."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_entity_nodes(story_id=STORY_ID, entities=ENTITIES)

    # Single UNWIND query — all entities in one transaction
    assert len(driver.session_instance.queries) == 1
    query, params = driver.session_instance.queries[0]
    assert "Entity" in query
    assert "MENTIONS" in query
    assert "UNWIND" in query
    assert params.get("story_id") == STORY_ID
    entities_param = params.get("entities")
    assert len(entities_param) == 2
    assert entities_param[0]["name"] == "CI pipeline"
    assert entities_param[1]["name"] == "deployment"


def test_save_entity_nodes_empty_list_is_noop():
    """save_entity_nodes does nothing when entities list is empty."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_entity_nodes(story_id=STORY_ID, entities=[])

    assert len(driver.session_instance.queries) == 0


def test_save_entity_nodes_raises_graph_error_on_failure():
    """save_entity_nodes raises GraphError when the driver raises."""
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
        adapter.save_entity_nodes(story_id=STORY_ID, entities=ENTITIES)


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
