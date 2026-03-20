"""Tests for Neo4jGraphAdapter."""

import pytest

from src.domain.models import TriadCoordinates, TriadPlacement
from src.ports.graph import GraphPort

STORY_ID = "story-abc"
TIMESTAMP = "2026-03-13T10:00:00Z"
TRIADS = [
    TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
    TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
    TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
]


class FakeResult:
    """Fake Neo4j query result supporting .data() and .single()."""

    def data(self) -> list:
        return []

    def single(self):
        return {"count": 0}


class FakeSession:
    """Records Cypher queries and parameters for inspection.

    Supports both direct session.run() and session.execute_write(tx_func)
    so that transactional and non-transactional adapters can both be tested.
    """

    def __init__(self):
        self.queries = []  # list of (query, params)

    def run(self, query: str, **params) -> "FakeResult":
        self.queries.append((query, params))
        return FakeResult()

    def execute_write(self, tx_func) -> None:
        """Run tx_func with self as the transaction object (records queries)."""
        tx_func(self)

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


# ── Tests for save_theme_nodes ────────────────────────────────────────────────

THEMES = ["automation friction", "  Developer Experience  ", "TOOLING RELIABILITY"]


def test_save_theme_nodes_creates_theme_nodes_and_relationships():
    """save_theme_nodes creates Theme nodes and HAS_THEME relationships via UNWIND.

    Cypher must MATCH the Story before UNWINDing themes so that no orphan Theme
    nodes are created when the Story node is absent.
    """
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_theme_nodes(story_id=STORY_ID, themes=THEMES)

    assert len(driver.session_instance.queries) == 1
    query, params = driver.session_instance.queries[0]
    assert "Theme" in query
    assert "HAS_THEME" in query
    assert "UNWIND" in query
    # MATCH Story must appear before UNWIND in the query to avoid orphan nodes
    assert query.index("MATCH") < query.index("UNWIND")
    assert params.get("story_id") == STORY_ID
    themes_param = params.get("themes")
    assert len(themes_param) == 3


def test_save_theme_nodes_normalises_text():
    """Theme text is trimmed, lowercased, and whitespace-collapsed before MERGE."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_theme_nodes(story_id=STORY_ID, themes=["  Developer Experience  ", "TOOLING  RELIABILITY"])

    _, params = driver.session_instance.queries[0]
    normalised = [t["name"] for t in params["themes"]]
    assert "developer experience" in normalised
    assert "tooling  reliability" not in normalised  # internal whitespace collapsed
    assert "tooling reliability" in normalised


def test_save_theme_nodes_deduplicates_normalised_themes():
    """Themes that normalise to the same string are deduplicated before MERGE."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_theme_nodes(story_id=STORY_ID, themes=["Automation", "automation", "AUTOMATION"])

    _, params = driver.session_instance.queries[0]
    assert len(params["themes"]) == 1
    assert params["themes"][0]["name"] == "automation"


def test_save_theme_nodes_filters_whitespace_only_themes():
    """Themes that normalise to empty string (whitespace-only) are dropped silently."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_theme_nodes(story_id=STORY_ID, themes=["valid theme", "   ", "\t"])

    assert len(driver.session_instance.queries) == 1
    _, params = driver.session_instance.queries[0]
    names = [t["name"] for t in params["themes"]]
    assert "valid theme" in names
    assert "" not in names


def test_save_theme_nodes_all_whitespace_is_noop():
    """save_theme_nodes does nothing when all themes normalise to empty string."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_theme_nodes(story_id=STORY_ID, themes=["   ", "\t\n"])

    assert len(driver.session_instance.queries) == 0


def test_save_theme_nodes_empty_list_is_noop():
    """save_theme_nodes does nothing when themes list is empty."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_theme_nodes(story_id=STORY_ID, themes=[])

    assert len(driver.session_instance.queries) == 0


def test_save_theme_nodes_raises_graph_error_on_failure():
    """save_theme_nodes raises GraphError when the driver raises."""
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
        adapter.save_theme_nodes(story_id=STORY_ID, themes=["some theme"])


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


# ── Story 3.4: save_proximity_relationships ───────────────────────────────────

def test_save_proximity_relationships_empty_list_still_deletes_stale_edges():
    """save_proximity_relationships with empty pairs still issues a DELETE query.

    Stale edges must be removed even when no new pairs qualify, so that
    reprojection is always consistent.
    """
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_proximity_relationships(story_id=STORY_ID, pairs=[])

    assert len(driver.session_instance.queries) == 1
    query, params = driver.session_instance.queries[0]
    assert "DELETE" in query
    assert params.get("story_id") == STORY_ID


def test_save_proximity_relationships_emits_unwind_merge_cypher():
    """save_proximity_relationships issues UNWIND+MERGE for NEAR_IN_SIGNIFIER_SPACE."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter
    from src.domain.models import TriadProximity

    pair = TriadProximity(
        story_id_a="story-aaa",
        story_id_b="story-zzz",
        triad_id="workflow_nature",
        distance=0.2,
    )

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_proximity_relationships(story_id="story-aaa", pairs=[pair])

    assert len(driver.session_instance.queries) >= 1
    queries_text = " ".join(q for q, _ in driver.session_instance.queries)
    assert "NEAR_IN_SIGNIFIER_SPACE" in queries_text
    assert "UNWIND" in queries_text


def test_save_proximity_relationships_deletes_existing_edges_first():
    """save_proximity_relationships deletes stale edges before writing new ones."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter
    from src.domain.models import TriadProximity

    pair = TriadProximity(
        story_id_a="story-aaa",
        story_id_b="story-zzz",
        triad_id="workflow_nature",
        distance=0.2,
    )

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)

    adapter.save_proximity_relationships(story_id="story-aaa", pairs=[pair])

    # First query should be the DELETE
    first_query, first_params = driver.session_instance.queries[0]
    assert "DELETE" in first_query
    assert first_params.get("story_id") == "story-aaa"


def test_save_proximity_relationships_raises_graph_error_on_failure():
    """save_proximity_relationships raises GraphError when driver raises."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter
    from src.domain.models import TriadProximity
    from src.ports.errors import GraphError

    pair = TriadProximity(
        story_id_a="story-aaa",
        story_id_b="story-zzz",
        triad_id="workflow_nature",
        distance=0.2,
    )

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
        adapter.save_proximity_relationships(story_id="story-aaa", pairs=[pair])


# ── Story 4.1: find_story_ids_by_entity ──────────────────────────────────────

def test_find_story_ids_by_entity_emits_cypher_with_skip_limit():
    """find_story_ids_by_entity runs a Cypher query with SKIP and LIMIT."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)
    adapter.find_story_ids_by_entity("CI pipeline", limit=10, offset=20)

    assert len(driver.session_instance.queries) == 1
    query, params = driver.session_instance.queries[0]
    assert "SKIP" in query
    assert "LIMIT" in query
    assert params.get("limit") == 10
    assert params.get("offset") == 20


def test_find_story_ids_by_entity_case_insensitive():
    """Entity name lookup is case-insensitive."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)
    adapter.find_story_ids_by_entity("CI Pipeline", limit=10, offset=0)

    query, params = driver.session_instance.queries[0]
    assert "toLower" in query


def test_find_story_ids_by_entity_raises_graph_error_on_failure():
    """find_story_ids_by_entity raises GraphError when driver fails."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter
    from src.ports.errors import GraphError

    class FailingSession:
        def run(self, query, **params):
            raise Exception("Neo4j down")
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class FailingDriver:
        def session(self): return FailingSession()

    adapter = Neo4jGraphAdapter(driver=FailingDriver())
    with pytest.raises(GraphError):
        adapter.find_story_ids_by_entity("anything", limit=10, offset=0)


# ── Story 4.1: count_stories_by_entity ────────────────────────────────────────

def test_count_stories_by_entity_emits_count_query():
    """count_stories_by_entity runs a COUNT query."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(driver=driver)
    adapter.count_stories_by_entity("CI pipeline")

    assert len(driver.session_instance.queries) == 1
    query, _ = driver.session_instance.queries[0]
    assert "COUNT" in query.upper()


def test_count_stories_by_entity_raises_graph_error_on_failure():
    """count_stories_by_entity raises GraphError when driver fails."""
    from src.adapters.neo4j_graph import Neo4jGraphAdapter
    from src.ports.errors import GraphError

    class FailingSession:
        def run(self, query, **params):
            raise Exception("Neo4j down")
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class FailingDriver:
        def session(self): return FailingSession()

    adapter = Neo4jGraphAdapter(driver=FailingDriver())
    with pytest.raises(GraphError):
        adapter.count_stories_by_entity("anything")
