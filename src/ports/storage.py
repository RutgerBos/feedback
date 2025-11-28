"""
StoragePort interface for story persistence.

This port defines the contract for storing and retrieving stories,
independent of the actual storage implementation (MongoDB, PostgreSQL, etc).
"""

from abc import ABC, abstractmethod
from src.domain.models import Story


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
    - Interface designed for current needs (Story 1.1)
    - Will expand with query methods as needed
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
