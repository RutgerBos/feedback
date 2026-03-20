"""
Neo4j graph adapter implementing GraphPort.
"""

from typing import Any

from src.domain.models import TriadPlacement, TriadProximity
from src.ports.errors import GraphError
from src.ports.graph import GraphPort


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
        self, story_id: str, entities: list[dict[str, Any]]
    ) -> None:
        """Create Entity nodes and MENTIONS relationships for a story.

        Notes:
        - Entity identity is name-only (POC decision). Type is a mutable annotation;
          if the LLM labels the same name differently across stories, the last write wins.
          This should be revisited if entity deduplication becomes a requirement.
        - All entities are written in a single transaction for atomicity.
        """
        if not entities:
            return
        entities_data = [
            {"name": e.get("name", ""), "entity_type": e.get("type", "")}
            for e in entities
        ]
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    UNWIND $entities AS entity
                    MERGE (e:Entity {name: entity.name})
                    SET e.type = entity.entity_type
                    WITH e
                    MATCH (s:Story {story_id: $story_id})
                    MERGE (s)-[:MENTIONS]->(e)
                    """,
                    entities=entities_data,
                    story_id=story_id,
                )
        except Exception as e:
            raise GraphError(f"Failed to save entity nodes: {e}") from e

    def save_theme_nodes(self, story_id: str, themes: list[str]) -> None:
        """Create Theme nodes and HAS_THEME relationships for a story.

        Notes:
        - Theme identity is the normalised text (trimmed, lowercased, whitespace-collapsed).
        - All themes written in a single transaction for atomicity.
        """
        if not themes:
            return
        normalised = list(dict.fromkeys(
            n for n in (" ".join(t.strip().lower().split()) for t in themes) if n
        ))
        if not normalised:
            return
        themes_data = [{"name": n} for n in normalised]
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MATCH (s:Story {story_id: $story_id})
                    WITH s
                    UNWIND $themes AS theme
                    MERGE (t:Theme {name: theme.name})
                    MERGE (s)-[:HAS_THEME]->(t)
                    """,
                    themes=themes_data,
                    story_id=story_id,
                )
        except Exception as e:
            raise GraphError(f"Failed to save theme nodes: {e}") from e

    def save_story_node(
        self, story_id: str, triads: list[TriadPlacement], timestamp: str
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

    def save_proximity_relationships(
        self, story_id: str, pairs: list[TriadProximity]
    ) -> None:
        """Replace NEAR_IN_SIGNIFIER_SPACE edges for a story.

        Deletes all existing proximity edges touching story_id, then writes
        the new qualifying pairs. Empty pairs list still removes stale edges.

        Notes:
        - Relationship is directed (a)->(b) where story_id_a < story_id_b (canonical).
        - triad_id is part of the relationship identity to allow one edge per triad pair.
        - distance and weight are overwritten on every reprojection.
        """
        pairs_data = [
            {
                "story_id_a": p.story_id_a,
                "story_id_b": p.story_id_b,
                "triad_id": p.triad_id,
                "distance": p.distance,
                "weight": p.weight,
            }
            for p in pairs
        ]

        def _replace(tx: Any) -> None:
            tx.run(
                """
                MATCH (s:Story {story_id: $story_id})-[r:NEAR_IN_SIGNIFIER_SPACE]-()
                DELETE r
                """,
                story_id=story_id,
            )
            if pairs_data:
                tx.run(
                    """
                    UNWIND $pairs AS pair
                    MATCH (a:Story {story_id: pair.story_id_a})
                    MATCH (b:Story {story_id: pair.story_id_b})
                    MERGE (a)-[r:NEAR_IN_SIGNIFIER_SPACE {triad_id: pair.triad_id}]->(b)
                    SET r.distance = pair.distance, r.weight = pair.weight
                    """,
                    pairs=pairs_data,
                )

        try:
            with self._driver.session() as session:
                session.execute_write(_replace)
        except Exception as e:
            raise GraphError(f"Failed to save proximity relationships: {e}") from e

    def find_story_ids_by_entity(
        self, entity_name: str, limit: int, offset: int
    ) -> list[str]:
        """Return story IDs for stories mentioning entity_name, newest first."""
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (e:Entity)<-[:MENTIONS]-(s:Story)
                    WHERE toLower(e.name) = toLower($entity_name)
                    RETURN DISTINCT s.story_id AS story_id, s.timestamp AS ts
                    ORDER BY ts DESC, story_id DESC
                    SKIP $offset LIMIT $limit
                    """,
                    entity_name=entity_name,
                    offset=offset,
                    limit=limit,
                )
                return [row["story_id"] for row in result.data()]
        except Exception as e:
            raise GraphError(f"Failed to find stories by entity: {e}") from e

    def count_stories_by_entity(self, entity_name: str) -> int:
        """Return total count of stories mentioning entity_name."""
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (e:Entity)<-[:MENTIONS]-(s:Story)
                    WHERE toLower(e.name) = toLower($entity_name)
                    RETURN COUNT(DISTINCT s) AS count
                    """,
                    entity_name=entity_name,
                )
                record = result.single()
                return record["count"] if record else 0
        except Exception as e:
            raise GraphError(f"Failed to count stories by entity: {e}") from e

    def find_themes_ranked(
        self,
        limit: int,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[tuple[str, int]]:
        """Return themes sorted by story count descending, optionally filtered by date."""
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (s:Story)-[:HAS_THEME]->(t:Theme)
                    WHERE ($from_date IS NULL OR s.timestamp >= $from_date)
                      AND ($to_date   IS NULL OR s.timestamp <= $to_date)
                    RETURN t.name AS name, COUNT(DISTINCT s) AS story_count
                    ORDER BY story_count DESC, name ASC
                    LIMIT $limit
                    """,
                    from_date=from_date,
                    to_date=to_date,
                    limit=limit,
                )
                return [(row["name"], row["story_count"]) for row in result.data()]
        except Exception as e:
            raise GraphError(f"Failed to find ranked themes: {e}") from e

    def find_story_ids_by_theme(
        self,
        theme_name: str,
        limit: int,
        offset: int,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[str]:
        """Return story IDs for stories with the given theme, newest first."""
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (s:Story)-[:HAS_THEME]->(t:Theme)
                    WHERE toLower(t.name) = toLower($theme_name)
                      AND ($from_date IS NULL OR s.timestamp >= $from_date)
                      AND ($to_date   IS NULL OR s.timestamp <= $to_date)
                    RETURN s.story_id AS story_id
                    ORDER BY s.timestamp DESC, s.story_id DESC
                    SKIP $offset LIMIT $limit
                    """,
                    theme_name=theme_name,
                    from_date=from_date,
                    to_date=to_date,
                    offset=offset,
                    limit=limit,
                )
                return [row["story_id"] for row in result.data()]
        except Exception as e:
            raise GraphError(f"Failed to find stories by theme: {e}") from e

    def count_stories_by_theme(self, theme_name: str) -> int:
        """Return total count of stories with the given theme."""
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (s:Story)-[:HAS_THEME]->(t:Theme)
                    WHERE toLower(t.name) = toLower($theme_name)
                    RETURN COUNT(DISTINCT s) AS count
                    """,
                    theme_name=theme_name,
                )
                record = result.single()
                return record["count"] if record else 0
        except Exception as e:
            raise GraphError(f"Failed to count stories by theme: {e}") from e
