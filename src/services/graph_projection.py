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
    - Project processed story concepts into the knowledge graph
    - Coordinate proximity relationships for projected stories
    - Keep enrichment processing available when graph projection fails

    Collaborators:
    - StoragePort
    - GraphPort
    - ProximityCalculationService
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
