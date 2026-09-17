"""
EntityExtractionService: orchestrates LLM entity extraction for stories.
"""

import logging
from typing import TYPE_CHECKING

from src.ports.errors import LLMError
from src.ports.llm import LLMPort
from src.ports.storage import StoragePort

if TYPE_CHECKING:
    from src.services.graph_projection import GraphProjectionService

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """
    Responsibilities:
    - Enrich stories with extracted entities and themes
    - Preserve a consistent processing outcome when enrichment fails
    - Coordinate graph projection after successful enrichment

    Collaborators:
    - StoragePort
    - LLMPort
    - GraphProjectionService
    """

    def __init__(
        self,
        storage: StoragePort,
        llm: LLMPort,
        graph_projection: "GraphProjectionService | None" = None,
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.graph_projection = graph_projection

    def extract_for_story(self, story_id: str) -> bool:
        """
        Run entity extraction for a single story and persist results.

        Args:
            story_id: ID of the story to process

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        try:
            extraction = self.llm.extract_entities(story.story_text)
            entities = extraction.entities
            themes = self.llm.extract_themes(story.story_text)
            entity_status = "processed"
        except LLMError as e:
            logger.warning("Entity extraction failed for story %s: %s", story_id, e)
            entities = []
            themes = []
            entity_status = "failed"

        self.storage.update_story_entities(
            story_id=story_id,
            entities=entities,
            themes=themes,
            entity_status=entity_status,
        )

        if entity_status == "processed" and self.graph_projection is not None:
            self.graph_projection.project_story(story_id)

        return entity_status == "processed"
