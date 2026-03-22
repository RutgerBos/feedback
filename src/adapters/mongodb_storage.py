"""
MongoDB storage adapter implementing StoragePort.

This adapter provides concrete MongoDB implementation of the StoragePort interface.
"""

from datetime import datetime
from typing import Any

from pymongo.database import Database

from src.domain.models import (
    ContextMetadata,
    ParticipantMetadata,
    SentimentAnalysis,
    Story,
    StoryMetadata,
    StorySignification,
    TriadCoordinates,
    TriadPlacement,
    TriadResponseItem,
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

    def count_stories(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Return the number of stories matching the optional date filter."""
        try:
            return self.collection.count_documents(
                self._date_filter(from_date, to_date)
            )
        except Exception as e:
            raise StorageError(f"Failed to count stories: {e}") from e

    def list_stories(
        self,
        limit: int = 20,
        offset: int = 0,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[Story]:
        """
        Retrieve a paginated list of stories from MongoDB, newest first,
        optionally filtered by date range.

        Raises:
            StorageError: If retrieval fails
        """
        try:
            cursor = (
                self.collection.find(self._date_filter(from_date, to_date))
                .sort("timestamp", -1)
                .skip(offset)
                .limit(limit)
            )
            return [self._document_to_story(doc) for doc in cursor]
        except Exception as e:
            raise StorageError(f"Failed to list stories: {e}") from e

    @staticmethod
    def _date_filter(
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> dict:
        """Build a MongoDB timestamp filter from optional date bounds."""
        if from_date is None and to_date is None:
            return {}
        ts: dict = {}
        if from_date is not None:
            ts["$gte"] = from_date
        if to_date is not None:
            ts["$lte"] = to_date
        return {"timestamp": ts}

    def update_story_entities(
        self,
        story_id: str,
        entities: list[dict[str, Any]],
        themes: list[str],
        entity_status: str,
    ) -> None:
        """
        Update a story's extracted entities, themes, and entity status in MongoDB.

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
                    "entity_status": entity_status,
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
        sentiment_status: str,
    ) -> None:
        """
        Update a story's sentiment analysis result and sentiment status in MongoDB.

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
                    "sentiment_status": sentiment_status,
                }},
            )
            if result.matched_count == 0:
                raise NotFoundError(f"Story not found: {story_id}")
        except NotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to update story sentiment: {e}") from e

    def find_story_ids_requiring_processing(self) -> list[str]:
        """
        Return IDs of stories where entity_status or sentiment_status is not 'processed'.
        Used by the background worker sweep to catch stories missed by the queue.
        """
        docs = self.collection.find(
            {"$or": [
                {"entity_status": {"$ne": "processed"}},
                {"sentiment_status": {"$ne": "processed"}},
            ]},
            {"_id": 1},
        )
        return [str(doc["_id"]) for doc in docs]

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

        # Convert V1 metadata if present
        metadata_dict = None
        if story.metadata:
            metadata_dict = {
                "user_pseudonym": story.metadata.user_pseudonym,
                "department": story.metadata.department,
                "role": story.metadata.role,
                "tool_context": story.metadata.tool_context,
            }

        # Convert V2 context metadata if present
        context_dict = None
        if story.context:
            context_dict = {
                "department": story.context.department,
                "role": story.context.role,
                "tool_context": story.context.tool_context,
            }

        # Convert V2 participant metadata if present
        participant_dict = None
        if story.participant:
            participant_dict = {
                "user_pseudonym": story.participant.user_pseudonym,
            }

        # Convert V2 signification if present
        signification_dict = None
        if story.signification:
            signification_dict = {
                "headline": story.signification.headline,
                "responses": [
                    {
                        "kind": r.kind,
                        "signifier_id": r.signifier_id,
                        "coordinates": {"x": r.coordinates.x, "y": r.coordinates.y},
                    }
                    for r in story.signification.responses
                ],
            }

        sentiment_dict = None
        if story.sentiment is not None:
            sentiment_dict = {
                "emotion_markers": story.sentiment.emotion_markers,
                "process_sentiment": story.sentiment.process_sentiment,
                "outcome_sentiment": story.sentiment.outcome_sentiment,
            }

        return {
            "schema_version": story.schema_version,
            "story_text": story.story_text,
            "triads": triads_list,
            "metadata": metadata_dict,
            "signification": signification_dict,
            "context": context_dict,
            "participant": participant_dict,
            "timestamp": story.timestamp,
            "processing_status": story.processing_status,
            "entity_status": story.entity_status,
            "sentiment_status": story.sentiment_status,
            "entities": story.entities,
            "themes": story.themes,
            "sentiment": sentiment_dict,
        }

    def _document_to_story(self, document: dict[str, Any]) -> Story:
        """
        Convert MongoDB document to Story domain model.

        Handles both V1 (schema_version absent or 1) and V2 documents.

        Args:
            document: MongoDB document

        Returns:
            Story: Story domain object
        """
        schema_version = document.get("schema_version", 1)

        # Convert triads (V1 compat)
        triads = [
            TriadPlacement(
                triad_id=t["triad_id"],
                coordinates=TriadCoordinates(
                    x=t["coordinates"]["x"], y=t["coordinates"]["y"]
                ),
            )
            for t in document.get("triads", [])
        ]

        # Convert V1 metadata if present
        metadata = None
        if document.get("metadata"):
            metadata = StoryMetadata(
                user_pseudonym=document["metadata"].get("user_pseudonym"),
                department=document["metadata"].get("department"),
                role=document["metadata"].get("role"),
                tool_context=document["metadata"].get("tool_context"),
            )

        # Convert V2 context metadata if present
        context = None
        if document.get("context"):
            c = document["context"]
            context = ContextMetadata(
                department=c.get("department"),
                role=c.get("role"),
                tool_context=c.get("tool_context"),
            )

        # Convert V2 participant metadata if present
        participant = None
        if document.get("participant"):
            p = document["participant"]
            participant = ParticipantMetadata(
                user_pseudonym=p.get("user_pseudonym"),
            )

        # Convert V2 signification if present
        signification = None
        if document.get("signification"):
            sig = document["signification"]
            responses = [
                TriadResponseItem(
                    kind=r["kind"],
                    signifier_id=r["signifier_id"],
                    coordinates=TriadCoordinates(
                        x=r["coordinates"]["x"], y=r["coordinates"]["y"]
                    ),
                )
                for r in sig.get("responses", [])
            ]
            signification = StorySignification(
                headline=sig.get("headline"),
                responses=responses,
            )

        # Convert sentiment if present.
        # Use a try/except so that legacy docs with free-form sentiment values
        # (stored before the SentimentLabel constraint was introduced) degrade
        # gracefully to sentiment=None rather than crashing the read path.
        sentiment = None
        if document.get("sentiment"):
            s = document["sentiment"]
            try:
                sentiment = SentimentAnalysis(
                    emotion_markers=s.get("emotion_markers", []),
                    process_sentiment=s["process_sentiment"],
                    outcome_sentiment=s["outcome_sentiment"],
                )
            except (ValueError, KeyError):
                pass  # Legacy free-form value — treat as unanalysed

        return Story(
            id=document["_id"],
            story_text=document["story_text"],
            schema_version=schema_version,
            triads=triads,
            metadata=metadata,
            signification=signification,
            context=context,
            participant=participant,
            timestamp=document["timestamp"],
            processing_status=document.get("processing_status", "pending"),
            entity_status=document.get("entity_status", "pending"),
            sentiment_status=document.get("sentiment_status", "pending"),
            entities=document.get("entities", []),
            themes=document.get("themes", []),
            sentiment=sentiment,
        )
