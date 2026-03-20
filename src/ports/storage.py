"""
StoragePort interface for story persistence.

This port defines the contract for storing and retrieving stories,
independent of the actual storage implementation (MongoDB, PostgreSQL, etc).
"""

from abc import ABC, abstractmethod
from typing import Any

from src.domain.models import SentimentAnalysis, Story


class StoragePort(ABC):
    """
    Responsibilities:
    - Persist story data
    - Retrieve story data by ID
    - Provide atomic operations for story storage

    Collaborators:
    - Story (domain model)

    Notes:
    - No knowledge of storage implementation (MongoDB, PostgreSQL, etc)
    - Operations are atomic
    - May raise StorageError for infrastructure issues
    - May raise NotFoundError if story doesn't exist
    """

    @abstractmethod
    def save_story(self, story: Story) -> str:
        """
        Save a story and return its assigned ID.

        Args:
            story: Story domain object to persist

        Returns:
            str: The story's ID (may be generated if not set)

        Raises:
            StorageError: If persistence fails due to infrastructure issues
        """
        pass

    @abstractmethod
    def get_story(self, story_id: str) -> Story:
        """
        Retrieve a story by its ID.

        Args:
            story_id: Unique identifier for the story

        Returns:
            Story: The retrieved story domain object

        Raises:
            NotFoundError: If no story exists with the given ID
            StorageError: If retrieval fails due to infrastructure issues
        """
        pass

    @abstractmethod
    def count_stories(self) -> int:
        """
        Return the total number of stories in storage.

        Returns:
            int: Total story count

        Raises:
            StorageError: If the count fails due to infrastructure issues
        """
        pass

    @abstractmethod
    def list_stories(self, limit: int = 20, offset: int = 0) -> list[Story]:
        """
        Retrieve a paginated list of stories, newest first.

        Args:
            limit: Maximum number of stories to return (default 20)
            offset: Number of stories to skip (default 0)

        Returns:
            List[Story]: List of story domain objects

        Raises:
            StorageError: If retrieval fails due to infrastructure issues
        """
        pass

    @abstractmethod
    def update_story_entities(
        self,
        story_id: str,
        entities: list[dict[str, Any]],
        themes: list[str],
        processing_status: str,
    ) -> None:
        """
        Update a story's extracted entities, themes, and processing status.

        Args:
            story_id: Unique identifier for the story
            entities: List of extracted entity dicts (name, type)
            themes: List of extracted theme strings
            processing_status: New processing status ("processed" or "failed")

        Raises:
            NotFoundError: If no story exists with the given ID
            StorageError: If update fails due to infrastructure issues
        """
        pass

    @abstractmethod
    def update_story_sentiment(
        self,
        story_id: str,
        sentiment: SentimentAnalysis | None,
        processing_status: str,
    ) -> None:
        """
        Update a story's sentiment analysis result and processing status.

        Args:
            story_id: Unique identifier for the story
            sentiment: SentimentAnalysis result, or None if extraction failed
            processing_status: New processing status ("processed" or "failed")

        Raises:
            NotFoundError: If no story exists with the given ID
            StorageError: If update fails due to infrastructure issues
        """
        pass
