"""
StoryProcessingService: orchestrates graph save, entity extraction, and sentiment extraction.
"""

from src.domain.models import TriadCoordinates, TriadPlacement
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort
from src.services.entity_extraction import EntityExtractionService
from src.services.sentiment_extraction import SentimentExtractionService


class StoryProcessingService:
    """
    Responsibilities:
    - Coordinate graph projection and narrative enrichment for a story

    Collaborators:
    - StoragePort
    - GraphPort
    - EntityExtractionService
    - SentimentExtractionService
    """

    def __init__(
        self,
        storage: StoragePort,
        graph: GraphPort,
        entity_service: EntityExtractionService,
        sentiment_service: SentimentExtractionService,
    ) -> None:
        self.storage = storage
        self.graph = graph
        self.entity_service = entity_service
        self.sentiment_service = sentiment_service

    def process(self, story_id: str) -> bool:
        """
        Run full post-submission processing for a story.

        Raises:
            GraphError: if saving the story node to the graph fails
            NotFoundError: if the story does not exist in storage
        """
        story = self.storage.get_story(story_id)
        triads = [
            TriadPlacement(
                triad_id=r.signifier_id,
                coordinates=TriadCoordinates(x=r.coordinates.x, y=r.coordinates.y),
            )
            for r in (story.signification.responses if story.signification else [])
        ]
        self.graph.save_story_node(
            story_id=story.id,
            triads=triads,
            timestamp=story.timestamp.isoformat(),
        )
        entities_processed = self.entity_service.extract_for_story(story_id)
        sentiment_processed = self.sentiment_service.extract_for_story(story_id)
        return entities_processed is not False and sentiment_processed is not False
