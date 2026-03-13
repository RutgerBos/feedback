"""
EntityExtractionService: orchestrates LLM entity extraction for stories.
"""

import logging
from typing import TYPE_CHECKING, Optional
from src.ports.storage import StoragePort
from src.ports.llm import LLMPort
from src.ports.errors import LLMError

if TYPE_CHECKING:
    from src.services.graph_projection import GraphProjectionService

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """
    Responsibilities:
    - Retrieve a story from storage
    - Call LLM to extract entities (via extract_entities())
    - Call LLM to extract themes (via extract_themes())
    - Persist extraction results back to storage
    - Handle LLM failures gracefully (log, store empty results, set status)

    Collaborators:
    - StoragePort (to retrieve and update stories)
    - LLMPort (to extract entities and themes via separate calls)
    - GraphProjectionService (optional; projects entities into graph after extraction)

    Notes:
    - Failure is atomic: if either LLM call fails, both results are stored empty
    - Failed extractions do NOT raise — caller is never blocked
    - NotFoundError from storage IS propagated (caller must handle)
    - graph_projection is optional for backwards compatibility
    """

    def __init__(
        self,
        storage: StoragePort,
        llm: LLMPort,
        graph_projection: "Optional[GraphProjectionService]" = None,
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.graph_projection = graph_projection

    def extract_for_story(self, story_id: str) -> None:
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
            processing_status = "processed"
        except LLMError as e:
            logger.warning("Entity extraction failed for story %s: %s", story_id, e)
            entities = []
            themes = []
            processing_status = "failed"

        self.storage.update_story_entities(
            story_id=story_id,
            entities=entities,
            themes=themes,
            processing_status=processing_status,
        )

        if processing_status == "processed" and self.graph_projection is not None:
            self.graph_projection.save_entities_for_story(story_id)
