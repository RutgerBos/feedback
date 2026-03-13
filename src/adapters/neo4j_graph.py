"""
Neo4j graph adapter implementing GraphPort.
"""

from typing import Any, List

from src.ports.graph import GraphPort
from src.ports.errors import GraphError
from src.domain.models import TriadPlacement


class Neo4jGraphAdapter(GraphPort):
    """
    Responsibilities:
    - Create story nodes in Neo4j
    - Translate domain objects to Cypher queries

    Collaborators:
    - neo4j.Driver (injected for testability)
    - GraphPort (interface)

    Notes:
    - Driver is injected; no direct neo4j import at module level
    - Raises GraphError on any driver failure
    - Story nodes only for Story 3.1; entity/theme nodes added in 3.2/3.3
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def save_story_node(
        self, story_id: str, triads: List[TriadPlacement], timestamp: str
    ) -> None:
        """Create or update a Story node in Neo4j."""
        triads_data = [
            {
                "triad_id": t.triad_id,
                "x": t.coordinates.x,
                "y": t.coordinates.y,
            }
            for t in triads
        ]
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MERGE (s:Story {story_id: $story_id})
                    SET s.timestamp = $timestamp,
                        s.triads = $triads
                    """,
                    story_id=story_id,
                    timestamp=timestamp,
                    triads=triads_data,
                )
        except Exception as e:
            raise GraphError(f"Failed to save story node: {e}") from e
