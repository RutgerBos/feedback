"""
MongoDB storage adapter implementing StoragePort.

This adapter provides concrete MongoDB implementation of the StoragePort interface.
"""

from typing import Any

from pymongo.database import Database

from src.domain.models import (
    SentimentAnalysis,
    Story,
    StoryMetadata,
    TriadCoordinates,
    TriadPlacement,
)
from src.ports.errors import NotFoundError, StorageError
from src.ports.storage import StoragePort


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

    def count_stories(self) -> int:
        """Return the total number of stories in the collection."""
        try:
            return self.collection.count_documents({})
        except Exception as e:
            raise StorageError(f"Failed to count stories: {e}") from e

    def list_stories(self, limit: int = 20, offset: int = 0) -> list[Story]:
        """
        Retrieve a paginated list of stories from MongoDB, newest first.

        Args:
            limit: Maximum number of stories to return
            offset: Number of stories to skip

        Returns:
            List[Story]: List of story domain objects

        Raises:
            StorageError: If retrieval fails
        """
        try:
            cursor = (
                self.collection.find()
                .sort("timestamp", -1)
                .skip(offset)
                .limit(limit)
            )
            return [self._document_to_story(doc) for doc in cursor]
        except Exception as e:
            raise StorageError(f"Failed to list stories: {e}") from e

    def update_story_entities(
        self,
        story_id: str,
        entities: list[dict[str, Any]],
        themes: list[str],
        processing_status: str,
    ) -> None:
        """
        Update a story's extracted entities, themes, and processing status in MongoDB.

        Raises:
            NotFoundError: If no story exists with the given ID
            StorageError: If update fails
        """
        try:
            result = self.collection.update_one(
                {"_id": story_id},
                {"$set": {
                    "entities": entities,
                    "themes": themes,
                    "processing_status": processing_status,
                }},
            )
            if result.matched_count == 0:
                raise NotFoundError(f"Story not found: {story_id}")
        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to update story entities: {e}") from e

    def update_story_sentiment(
        self,
        story_id: str,
        sentiment: SentimentAnalysis | None,
        processing_status: str,
    ) -> None:
        """
        Update a story's sentiment analysis result and processing status in MongoDB.

        Raises:
            NotFoundError: If no story exists with the given ID
            StorageError: If update fails
        """
        try:
            sentiment_doc = None
            if sentiment is not None:
                sentiment_doc = {
                    "emotion_markers": sentiment.emotion_markers,
                    "process_sentiment": sentiment.process_sentiment,
                    "outcome_sentiment": sentiment.outcome_sentiment,
                }
            result = self.collection.update_one(
                {"_id": story_id},
                {"$set": {
                    "sentiment": sentiment_doc,
                    "processing_status": processing_status,
                }},
            )
            if result.matched_count == 0:
                raise NotFoundError(f"Story not found: {story_id}")
        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to update story sentiment: {e}") from e

    def _story_to_document(self, story: Story) -> dict[str, Any]:
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

        sentiment_dict = None
        if story.sentiment is not None:
            sentiment_dict = {
                "emotion_markers": story.sentiment.emotion_markers,
                "process_sentiment": story.sentiment.process_sentiment,
                "outcome_sentiment": story.sentiment.outcome_sentiment,
            }

        return {
            "story_text": story.story_text,
            "triads": triads_list,
            "metadata": metadata_dict,
            "timestamp": story.timestamp,
            "processing_status": story.processing_status,
            "entities": story.entities,
            "themes": story.themes,
            "sentiment": sentiment_dict,
        }

    def _document_to_story(self, document: dict[str, Any]) -> Story:
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

        # Convert sentiment if present
        sentiment = None
        if document.get("sentiment"):
            s = document["sentiment"]
            sentiment = SentimentAnalysis(
                emotion_markers=s.get("emotion_markers", []),
                process_sentiment=s["process_sentiment"],
                outcome_sentiment=s["outcome_sentiment"],
            )

        return Story(
            id=document["_id"],
            story_text=document["story_text"],
            triads=triads,
            metadata=metadata,
            timestamp=document["timestamp"],
            processing_status=document.get("processing_status", "pending"),
            entities=document.get("entities", []),
            themes=document.get("themes", []),
            sentiment=sentiment,
        )
