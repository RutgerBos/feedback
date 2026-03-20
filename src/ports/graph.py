"""
GraphPort interface for knowledge graph operations.

This port defines the contract for building and querying the knowledge graph,
independent of the actual graph database (Neo4j, Neptune, etc).
"""

from abc import ABC, abstractmethod
from typing import Any

from src.domain.models import TriadPlacement, TriadProximity


class GraphPort(ABC):
    """
    Responsibilities:
    - Create story nodes in knowledge graph
    - Create entity and theme nodes
    - Create relationships between nodes
    - Create proximity relationships between stories
    - Support graph queries (added as needed)

    Collaborators:
    - TriadPlacement (domain model)
    - TriadProximity (domain model)

    Notes:
    - No knowledge of graph database implementation (Neo4j, Neptune, etc)
    - Operates on domain concepts, not graph database primitives
    - Interface designed for current needs (Story nodes)
    - Will expand with relationship and query methods as needed
    - May raise GraphError for database failures
    """

    @abstractmethod
    def save_entity_nodes(
        self, story_id: str, entities: list[dict[str, Any]]
    ) -> None:
        """
        Create Entity nodes and MENTIONS relationships from a Story node.

        Args:
            story_id: ID of the story that mentions these entities
            entities: List of entity dicts with "name" and "type" keys

        Raises:
            GraphError: If node or relationship creation fails
        """
        pass

    @abstractmethod
    def save_theme_nodes(
        self, story_id: str, themes: list[str]
    ) -> None:
        """
        Create Theme nodes and HAS_THEME relationships from a Story node.

        Args:
            story_id: ID of the story that has these themes
            themes: List of theme strings (will be normalised before MERGE)

        Raises:
            GraphError: If node or relationship creation fails
        """
        pass

    @abstractmethod
    def save_story_node(
        self, story_id: str, triads: list[TriadPlacement], timestamp: str
    ) -> None:
        """
        Create a story node in the knowledge graph.

        Args:
            story_id: Unique identifier for the story
            triads: List of triad placements for the story
            timestamp: ISO8601 timestamp string

        Raises:
            GraphError: If node creation fails
        """
        pass

    @abstractmethod
    def save_proximity_relationships(
        self, story_id: str, pairs: list[TriadProximity]
    ) -> None:
        """
        Replace proximity relationships for a story.

        Deletes all existing NEAR_IN_SIGNIFIER_SPACE edges touching story_id,
        then creates new ones from pairs. Empty pairs list still deletes stale edges.

        Args:
            story_id: ID of the story being reprojected
            pairs: TriadProximity values to write (may be empty)

        Raises:
            GraphError: If deletion or creation fails
        """
        pass
