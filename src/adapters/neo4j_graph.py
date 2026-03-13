"""
Neo4j graph adapter implementing GraphPort.
"""

from typing import Any, Dict, List

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

    def save_entity_nodes(
        self, story_id: str, entities: List[Dict[str, Any]]
    ) -> None:
        """Create Entity nodes and MENTIONS relationships for a story."""
        if not entities:
            return
        try:
            with self._driver.session() as session:
                for entity in entities:
                    session.run(
                        """
                        MERGE (e:Entity {name: $name})
                        SET e.type = $entity_type
                        WITH e
                        MATCH (s:Story {story_id: $story_id})
                        MERGE (s)-[:MENTIONS]->(e)
                        """,
                        name=entity.get("name", ""),
                        entity_type=entity.get("type", ""),
                        story_id=story_id,
                    )
        except Exception as e:
            raise GraphError(f"Failed to save entity nodes: {e}") from e

    def save_story_node(
        self, story_id: str, triads: List[TriadPlacement], timestamp: str
    ) -> None:
        """Create or update a Story node in Neo4j.

        Notes:
        - Triad coordinates are not stored as node properties here: Neo4j
          properties cannot hold lists of maps. Triad data will be modelled
          as relationships/nodes in Story 3.4 (Link Stories by Triad Proximity).
        """
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MERGE (s:Story {story_id: $story_id})
                    SET s.timestamp = $timestamp
                    """,
                    story_id=story_id,
                    timestamp=timestamp,
                )
        except Exception as e:
            raise GraphError(f"Failed to save story node: {e}") from e
