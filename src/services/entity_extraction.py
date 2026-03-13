"""
EntityExtractionService: orchestrates LLM entity extraction for stories.
"""

import logging
from src.ports.storage import StoragePort
from src.ports.llm import LLMPort
from src.ports.errors import LLMError

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """
    Responsibilities:
    - Retrieve a story from storage
    - Call LLM to extract entities and themes
    - Persist extraction results back to storage
    - Handle LLM failures gracefully (log, store empty results, set status)

    Collaborators:
    - StoragePort (to retrieve and update stories)
    - LLMPort (to extract entities and themes)

    Notes:
    - Failed extractions do NOT raise — caller is never blocked
    - NotFoundError from storage IS propagated (caller must handle)
    """

    def __init__(self, storage: StoragePort, llm: LLMPort) -> None:
        self.storage = storage
        self.llm = llm

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
            themes = [
                name for t in extraction.themes
                if isinstance(t, dict) and (name := t.get("name", ""))
            ]
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
