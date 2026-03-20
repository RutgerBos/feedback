"""
SentimentExtractionService: orchestrates LLM sentiment extraction for stories.
"""

import logging

from src.ports.errors import LLMError
from src.ports.llm import LLMPort
from src.ports.storage import StoragePort

logger = logging.getLogger(__name__)


class SentimentExtractionService:
    """
    Responsibilities:
    - Retrieve a story from storage
    - Call LLM to extract sentiment (via extract_sentiment())
    - Persist sentiment results back to storage
    - Handle LLM failures gracefully (log, store None, set status to "failed")

    Collaborators:
    - StoragePort (to retrieve and update stories)
    - LLMPort (to extract sentiment)

    Notes:
    - Failure does NOT raise — caller is never blocked
    - NotFoundError from storage IS propagated (caller must handle)
    - Stores None sentiment on failure, not an empty/partial result
    """

    def __init__(self, storage: StoragePort, llm: LLMPort) -> None:
        self.storage = storage
        self.llm = llm

    def extract_for_story(self, story_id: str) -> None:
        """
        Run sentiment extraction for a single story and persist results.

        Args:
            story_id: ID of the story to process

        Raises:
            NotFoundError: If no story exists with the given ID
        """
        story = self.storage.get_story(story_id)

        try:
            sentiment = self.llm.extract_sentiment(story.story_text)
            processing_status = "processed"
        except LLMError as e:
            logger.warning("Sentiment extraction failed for story %s: %s", story_id, e)
            sentiment = None
            processing_status = "failed"

        self.storage.update_story_sentiment(
            story_id=story_id,
            sentiment=sentiment,
            processing_status=processing_status,
        )
