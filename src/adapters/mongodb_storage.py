"""
MongoDB storage adapter implementing StoragePort.

This adapter provides concrete MongoDB implementation of the StoragePort interface.
"""

from typing import Dict, Any
from pymongo.database import Database
from src.ports.storage import StoragePort
from src.domain.models import Story, TriadPlacement, TriadCoordinates, StoryMetadata


class NotFoundError(Exception):
    """Raised when a story is not found in storage."""

    pass


class StorageError(Exception):
    """Raised when storage operations fail."""

    pass


class MongoDBStorageAdapter(StoragePort):
    """
    Responsibilities:
    - Persist stories to MongoDB
    - Retrieve stories from MongoDB
    - Convert between domain models and MongoDB documents

    Collaborators:
    - Story (domain model)
    - MongoDB Database

    Notes:
    - Implements StoragePort interface
    - Uses _id field for story ID
    - Converts domain models to/from dict for storage
    - Collection name: "stories"
    """

    def __init__(self, database: Database):
        """
        Initialize MongoDB storage adapter.

        Args:
            database: MongoDB database instance
        """
        self.db = database
        self.collection = database.stories

    def save_story(self, story: Story) -> str:
        """
        Save a story to MongoDB.

        Args:
            story: Story domain object to persist

        Returns:
            str: The story's ID

        Raises:
            StorageError: If persistence fails
        """
        try:
            # Convert story to MongoDB document
            document = self._story_to_document(story)

            # Use story.id as MongoDB _id
            document["_id"] = story.id

            # Insert or replace
            self.collection.replace_one(
                {"_id": story.id}, document, upsert=True
            )

            return story.id

        except Exception as e:
            raise StorageError(f"Failed to save story: {e}") from e

    def get_story(self, story_id: str) -> Story:
        """
        Retrieve a story from MongoDB by ID.

        Args:
            story_id: Unique identifier for the story

        Returns:
            Story: The retrieved story domain object

        Raises:
            NotFoundError: If no story exists with the given ID
            StorageError: If retrieval fails
        """
        try:
            document = self.collection.find_one({"_id": story_id})

            if document is None:
                raise NotFoundError(f"Story not found: {story_id}")

            return self._document_to_story(document)

        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve story: {e}") from e

    def _story_to_document(self, story: Story) -> Dict[str, Any]:
        """
        Convert Story domain model to MongoDB document.

        Args:
            story: Story domain object

        Returns:
            dict: MongoDB document
        """
        # Convert triads
        triads_list = [
            {
                "triad_id": placement.triad_id,
                "coordinates": {
                    "x": placement.coordinates.x,
                    "y": placement.coordinates.y,
                },
            }
            for placement in story.triads
        ]

        # Convert metadata if present
        metadata_dict = None
        if story.metadata:
            metadata_dict = {
                "user_pseudonym": story.metadata.user_pseudonym,
                "department": story.metadata.department,
                "role": story.metadata.role,
                "tool_context": story.metadata.tool_context,
            }

        return {
            "story_text": story.story_text,
            "triads": triads_list,
            "metadata": metadata_dict,
            "timestamp": story.timestamp,
            "processing_status": story.processing_status,
        }

    def _document_to_story(self, document: Dict[str, Any]) -> Story:
        """
        Convert MongoDB document to Story domain model.

        Args:
            document: MongoDB document

        Returns:
            Story: Story domain object
        """
        # Convert triads
        triads = [
            TriadPlacement(
                triad_id=t["triad_id"],
                coordinates=TriadCoordinates(
                    x=t["coordinates"]["x"], y=t["coordinates"]["y"]
                ),
            )
            for t in document["triads"]
        ]

        # Convert metadata if present
        metadata = None
        if document.get("metadata"):
            metadata = StoryMetadata(
                user_pseudonym=document["metadata"].get("user_pseudonym"),
                department=document["metadata"].get("department"),
                role=document["metadata"].get("role"),
                tool_context=document["metadata"].get("tool_context"),
            )

        return Story(
            id=document["_id"],
            story_text=document["story_text"],
            triads=triads,
            metadata=metadata,
            timestamp=document["timestamp"],
            processing_status=document.get("processing_status", "pending"),
        )
