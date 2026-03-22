"""
GraphProjectionService: projects extracted story data into the knowledge graph.
"""

import logging
from typing import Any

from src.ports.errors import GraphError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort

logger = logging.getLogger(__name__)


class GraphProjectionService:
    """
    Responsibilities:
    - Read a processed story from storage (once per projection)
    - Project extracted entities into Neo4j as Entity nodes + MENTIONS relationships
    - Project extracted themes into Neo4j as Theme nodes + HAS_THEME relationships
    - Compute and persist proximity relationships to other stories
    - Handle graph failures gracefully (log, do not propagate)

    Collaborators:
    - StoragePort (to read story data)
    - GraphPort (to write graph nodes and relationships)
    - ProximityCalculationService (to write proximity relationships)

    Notes:
    - Only projects stories with processing_status == "processed"
    - GraphError is caught and logged — caller is never blocked
    - NotFoundError from storage IS propagated (caller must handle)
    - Story is loaded once and passed to each projection step to avoid redundant reads
    - proximity is optional; pass None to skip proximity calculation
    """

    def __init__(
        self,
        storage: StoragePort,
        graph: GraphPort,
        proximity: Any = None,
    ) -> None:
        self.storage = storage
        self.graph = graph
        self._proximity = proximity

    def project_story(self, story_id: str) -> None:
        """
        Project all extracted data from a processed story into the knowledge graph.

        Loads the story once, then runs entity, theme, and proximity projection.
        Each step is independent; a GraphError in one does not block the others.

        Args:
            story_id: ID of the story to project

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        if story.entity_status != "processed":
            return

        try:
            self.graph.save_entity_nodes(story_id=story_id, entities=story.entities)
        except GraphError as e:
            logger.warning("Entity graph projection failed for story %s: %s", story_id, e)

        try:
            self.graph.save_theme_nodes(story_id=story_id, themes=story.themes)
        except GraphError as e:
            logger.warning("Theme graph projection failed for story %s: %s", story_id, e)

        if self._proximity is not None:
            try:
                self._proximity.calculate_for_story(story_id)
            except GraphError as e:
                logger.warning("Proximity projection failed for story %s: %s", story_id, e)

    def save_entities_for_story(self, story_id: str) -> None:
        """
        Project entities from a processed story into the knowledge graph.

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        if story.entity_status != "processed":
            return

        try:
            self.graph.save_entity_nodes(story_id=story_id, entities=story.entities)
        except GraphError as e:
            logger.warning("Entity graph projection failed for story %s: %s", story_id, e)

    def save_themes_for_story(self, story_id: str) -> None:
        """
        Project themes from a processed story into the knowledge graph.

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        if story.entity_status != "processed":
            return

        try:
            self.graph.save_theme_nodes(story_id=story_id, themes=story.themes)
        except GraphError as e:
            logger.warning("Theme graph projection failed for story %s: %s", story_id, e)
