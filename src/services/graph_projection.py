"""
GraphProjectionService: projects extracted story data into the knowledge graph.
"""

import logging
from src.ports.storage import StoragePort
from src.ports.graph import GraphPort
from src.ports.errors import GraphError

logger = logging.getLogger(__name__)


class GraphProjectionService:
    """
    Responsibilities:
    - Read a processed story from storage
    - Project extracted entities into Neo4j as Entity nodes + MENTIONS relationships
    - Handle graph failures gracefully (log, do not propagate)

    Collaborators:
    - StoragePort (to read story data)
    - GraphPort (to write graph nodes and relationships)

    Notes:
    - Only projects stories with processing_status == "processed"
    - GraphError is caught and logged — caller is never blocked
    - NotFoundError from storage IS propagated (caller must handle)
    """

    def __init__(self, storage: StoragePort, graph: GraphPort) -> None:
        self.storage = storage
        self.graph = graph

    def project_story(self, story_id: str) -> None:
        """
        Project all extracted data from a processed story into the knowledge graph.

        Runs entity and theme projection in sequence. Each is independent;
        a GraphError in one does not block the other.

        Args:
            story_id: ID of the story to project

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        self.save_entities_for_story(story_id)
        self.save_themes_for_story(story_id)

    def save_entities_for_story(self, story_id: str) -> None:
        """
        Project entities from a processed story into the knowledge graph.

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        if story.processing_status != "processed":
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

        if story.processing_status != "processed":
            return

        try:
            self.graph.save_theme_nodes(story_id=story_id, themes=story.themes)
        except GraphError as e:
            logger.warning("Theme graph projection failed for story %s: %s", story_id, e)
