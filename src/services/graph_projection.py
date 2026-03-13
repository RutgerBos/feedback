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

    def save_entities_for_story(self, story_id: str) -> None:
        """
        Project entities from a processed story into the knowledge graph.

        Args:
            story_id: ID of the story to project

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        if story.processing_status != "processed":
            return

        try:
            self.graph.save_entity_nodes(story_id=story_id, entities=story.entities)
        except GraphError as e:
            logger.warning("Graph projection failed for story %s: %s", story_id, e)
