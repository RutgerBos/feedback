"""
GraphPort interface for knowledge graph operations.

This port defines the contract for building and querying the knowledge graph,
independent of the actual graph database (Neo4j, Neptune, etc).
"""

from abc import ABC, abstractmethod
from typing import List
from src.domain.models import TriadPlacement


class GraphPort(ABC):
    """
    Responsibilities:
    - Create story nodes in knowledge graph
    - Create entity and theme nodes
    - Create relationships between nodes
    - Support graph queries (added as needed)

    Collaborators:
    - TriadPlacement (domain model)

    Notes:
    - No knowledge of graph database implementation (Neo4j, Neptune, etc)
    - Operates on domain concepts, not graph database primitives
    - Interface designed for current needs (Story nodes)
    - Will expand with relationship and query methods as needed
    - May raise GraphError for database failures
    """

    @abstractmethod
    def save_story_node(
        self, story_id: str, triads: List[TriadPlacement], timestamp: str
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
