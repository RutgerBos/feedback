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
    <crc>
    responsibilities:
      - Enrich stories with process, outcome, and emotional sentiment
      - Preserve a consistent processing outcome when enrichment fails
    collaborators:
      - StoragePort
      - LLMPort
    </crc>
    """

    def __init__(self, storage: StoragePort, llm: LLMPort) -> None:
        self.storage = storage
        self.llm = llm

    def extract_for_story(self, story_id: str) -> bool:
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
            sentiment_status = "processed"
        except LLMError as e:
            logger.warning("Sentiment extraction failed for story %s: %s", story_id, e)
            sentiment = None
            sentiment_status = "failed"

        self.storage.update_story_sentiment(
            story_id=story_id,
            sentiment=sentiment,
            sentiment_status=sentiment_status,
        )
        return sentiment_status == "processed"
