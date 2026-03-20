"""
PatternQueryService: query stories by entity or theme pattern.
"""

from dataclasses import dataclass

from src.domain.models import Story
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


@dataclass
class EntityQueryResult:
    """
    Responsibilities:
    - Hold query results (stories + total count for pagination)

    Collaborators:
    - Story (domain model)

    Notes:
    - total is the full count, not just the page size
    """

    stories: list[Story]
    total: int


class PatternQueryService:
    """
    Responsibilities:
    - Query story IDs from graph by entity name
    - Load full story objects from storage
    - Return paginated results with total count

    Collaborators:
    - GraphPort (to query story IDs and totals)
    - StoragePort (to load full story objects)

    Notes:
    - GraphError propagates to caller (not swallowed)
    - Order of stories follows graph's ordering (timestamp DESC)
    """

    def __init__(self, graph: GraphPort, storage: StoragePort) -> None:
        self._graph = graph
        self._storage = storage

    def query_by_entity(
        self, entity_name: str, limit: int, offset: int
    ) -> EntityQueryResult:
        """
        Return paginated stories mentioning entity_name.

        Args:
            entity_name: Entity name to search (case-insensitive in graph)
            limit: Maximum stories to return
            offset: Number of stories to skip

        Returns:
            EntityQueryResult with stories list and total count

        Raises:
            GraphError: If the graph query fails
        """
        story_ids = self._graph.find_story_ids_by_entity(
            entity_name, limit=limit, offset=offset
        )
        total = self._graph.count_stories_by_entity(entity_name)
        stories = [self._storage.get_story(sid) for sid in story_ids]
        return EntityQueryResult(stories=stories, total=total)
