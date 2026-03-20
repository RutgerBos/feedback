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
    - Query stories by entity or theme
    - Count matching stories for pagination

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

    @abstractmethod
    def find_story_ids_by_entity(
        self, entity_name: str, limit: int, offset: int
    ) -> list[str]:
        """
        Return story IDs for stories mentioning entity_name (case-insensitive).

        Args:
            entity_name: Entity name to search for (matched case-insensitively)
            limit: Maximum number of IDs to return
            offset: Number of IDs to skip (for pagination)

        Returns:
            list of story_id strings, ordered by timestamp descending

        Raises:
            GraphError: If the query fails
        """
        pass

    @abstractmethod
    def count_stories_by_entity(self, entity_name: str) -> int:
        """
        Return total number of stories mentioning entity_name (case-insensitive).

        Args:
            entity_name: Entity name to count (matched case-insensitively)

        Returns:
            Total count of matching stories

        Raises:
            GraphError: If the query fails
        """
        pass

    @abstractmethod
    def find_themes_ranked(
        self,
        limit: int,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[tuple[str, int]]:
        """
        Return themes sorted by story count descending.

        Args:
            limit:     Maximum number of themes to return
            from_date: ISO8601 string — only count stories on or after this date
            to_date:   ISO8601 string — only count stories on or before this date

        Returns:
            List of (theme_name, story_count) tuples, sorted by count desc

        Raises:
            GraphError: If the query fails
        """
        pass

    @abstractmethod
    def find_story_ids_by_theme(
        self,
        theme_name: str,
        limit: int,
        offset: int,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[str]:
        """
        Return story IDs for stories with the given theme, newest first.

        Args:
            theme_name: Theme name to match (case-insensitive)
            limit:      Maximum number of IDs to return
            offset:     Number of IDs to skip
            from_date:  ISO8601 string — only include stories on or after this date
            to_date:    ISO8601 string — only include stories on or before this date

        Returns:
            List of story_id strings, ordered by timestamp DESC, story_id DESC

        Raises:
            GraphError: If the query fails
        """
        pass

    @abstractmethod
    def count_stories_by_theme(self, theme_name: str) -> int:
        """
        Return total number of stories with the given theme (case-insensitive).

        Args:
            theme_name: Theme name to count

        Returns:
            Total count of matching stories

        Raises:
            GraphError: If the query fails
        """
        pass

    @abstractmethod
    def find_entity_correlations(
        self,
        limit: int,
        threshold: float = 0.0,
        entity_type: str | None = None,
    ) -> list[tuple[str, str, int, float]]:
        """
        Return entity pairs ranked by Jaccard co-occurrence strength.

        Jaccard = |stories with both| / |stories with either|

        Args:
            limit:       Maximum number of pairs to return
            threshold:   Minimum Jaccard score (0.0–1.0) to include a pair
            entity_type: If given, restrict both entities to this type

        Returns:
            List of (entity_a, entity_b, co_count, jaccard) tuples,
            ordered by jaccard DESC, entity_a ASC, entity_b ASC

        Raises:
            GraphError: If the query fails
        """
        pass

    @abstractmethod
    def find_story_ids_by_entity_pair(
        self,
        entity_a: str,
        entity_b: str,
        limit: int,
        offset: int = 0,
    ) -> list[str]:
        """
        Return story IDs for stories that mention both entity_a and entity_b.

        Args:
            entity_a: First entity name (case-insensitive)
            entity_b: Second entity name (case-insensitive)
            limit:    Maximum number of IDs to return
            offset:   Number of IDs to skip

        Returns:
            List of story_id strings, ordered by timestamp DESC, story_id DESC

        Raises:
            GraphError: If the query fails
        """
        pass
