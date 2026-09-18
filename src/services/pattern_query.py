"""
PatternQueryService: query stories by entity or theme pattern.
"""

from dataclasses import dataclass, field

from src.domain.models import Story
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


@dataclass
class EntityQueryResult:
    """
    <crc>
    responsibilities:
      - Represent a paginated set of stories associated with an entity
    collaborators:
      - Story
    </crc>
    """

    stories: list[Story]
    total: int


@dataclass
class CorrelationPair:
    """
    <crc>
    responsibilities:
      - Represent the observed association between two entities
    collaborators: []
    </crc>
    """

    entity_a: str
    entity_b: str
    co_count: int
    jaccard: float
    sample_story_ids: list[str]


@dataclass
class CorrelationQueryResult:
    """
    <crc>
    responsibilities:
      - Represent ranked entity-pair correlations
    collaborators:
      - CorrelationPair
    </crc>
    """

    pairs: list[CorrelationPair] = field(default_factory=list)


@dataclass
class ThemeQueryResult:
    """
    <crc>
    responsibilities:
      - Represent ranked themes with supporting story samples
    collaborators: []
    </crc>
    """

    themes: list[dict] = field(default_factory=list)


class PatternQueryService:
    """
    <crc>
    responsibilities:
      - Provide ranked theme and entity-correlation evidence
      - Retrieve paginated stories associated with an entity
    collaborators:
      - GraphPort
      - StoragePort
    </crc>
    """

    def __init__(self, graph: GraphPort, storage: StoragePort) -> None:
        self._graph = graph
        self._storage = storage

    def query_themes(
        self,
        limit: int,
        sample_size: int,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> ThemeQueryResult:
        """
        Return themes ranked by story count with sample story IDs.

        Args:
            limit:      Maximum number of themes to return
            sample_size: Maximum story IDs to include per theme
            from_date:  ISO8601 string — filter stories on or after this date
            to_date:    ISO8601 string — filter stories on or before this date

        Returns:
            ThemeQueryResult with ranked themes list

        Raises:
            GraphError: If the graph query fails
        """
        ranked = self._graph.find_themes_ranked(
            limit=limit, from_date=from_date, to_date=to_date
        )
        themes = []
        for name, story_count in ranked:
            sample_ids = self._graph.find_story_ids_by_theme(
                name, limit=sample_size, offset=0,
                from_date=from_date, to_date=to_date,
            )
            themes.append({
                "name": name,
                "story_count": story_count,
                "sample_story_ids": sample_ids,
            })
        return ThemeQueryResult(themes=themes)

    def query_correlations(
        self,
        limit: int,
        sample_size: int,
        threshold: float = 0.0,
        entity_type: str | None = None,
    ) -> CorrelationQueryResult:
        """
        Return entity pairs ranked by Jaccard co-occurrence strength.

        Args:
            limit:       Maximum number of pairs to return
            sample_size: Maximum story IDs to include per pair
            threshold:   Minimum Jaccard score to include a pair
            entity_type: If given, restrict both entities to this type

        Returns:
            CorrelationQueryResult with ranked pairs list

        Raises:
            GraphError: If the graph query fails
        """
        ranked = self._graph.find_entity_correlations(
            limit=limit, threshold=threshold, entity_type=entity_type
        )
        pairs = []
        for entity_a, entity_b, co_count, jaccard in ranked:
            sample_ids = self._graph.find_story_ids_by_entity_pair(
                entity_a, entity_b, limit=sample_size
            )
            pairs.append(CorrelationPair(
                entity_a=entity_a,
                entity_b=entity_b,
                co_count=co_count,
                jaccard=jaccard,
                sample_story_ids=sample_ids,
            ))
        return CorrelationQueryResult(pairs=pairs)

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
