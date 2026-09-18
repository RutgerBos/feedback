"""
LLMPort interface for story analysis.

This port defines the contract for extracting entities, themes, and relationships
from stories, independent of the actual LLM provider (Claude, OpenAI, local model, etc).
EntityExtraction holds entity results only; themes are returned separately by extract_themes().
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.models import InsightContext, InsightOutput, QueryIntent, SentimentAnalysis


class EntityExtraction:
    """
    <crc>
    responsibilities:
      - Represent entities identified in one narrative-analysis pass
    collaborators: []
    </crc>
    """

    def __init__(self, entities: list[dict[str, Any]]):
        self.entities = entities


class LLMPort(ABC):
    """
    <crc>
    responsibilities:
      - Define structured narrative enrichment and synthesis
      - Define translation of natural-language questions into query intent
    collaborators:
      - EntityExtraction
      - SentimentAnalysis
    </crc>
    """

    @abstractmethod
    def extract_entities(self, story_text: str) -> EntityExtraction:
        """
        Extract entities from story text.

        Args:
            story_text: The narrative text to analyze

        Returns:
            EntityExtraction: Structured extraction results

        Raises:
            LLMError: If LLM API call fails or response cannot be parsed
        """
        pass

    @abstractmethod
    def extract_themes(self, story_text: str) -> list[str]:
        """
        Extract themes from story text.

        Args:
            story_text: The narrative text to analyze

        Returns:
            List[str]: List of theme descriptions (1-5 per story)

        Raises:
            LLMError: If LLM API call fails
        """
        pass

    @abstractmethod
    def extract_relationships(self, story_text: str) -> list[dict[str, Any]]:
        """
        Extract relationships between entities in story text.

        Args:
            story_text: The narrative text to analyze

        Returns:
            List[Dict]: Each dict has 'source', 'target', 'relationship' keys

        Raises:
            LLMError: If LLM API call fails
        """
        pass

    @abstractmethod
    def extract_sentiment(self, story_text: str) -> "SentimentAnalysis":
        """
        Extract sentiment and emotional tone from story text.

        Args:
            story_text: The narrative text to analyze

        Returns:
            SentimentAnalysis: emotion markers, process sentiment, outcome sentiment

        Raises:
            LLMError: If LLM API call fails or response cannot be parsed
        """
        pass

    @abstractmethod
    def synthesize_insights(self, context: "InsightContext") -> "InsightOutput":
        """
        Generate a narrative insight from structured pattern evidence.

        Args:
            context: InsightContext with query, entity, story excerpts, theme counts,
                     and sentiment summary

        Returns:
            InsightOutput: narrative explanation and optional caveats

        Raises:
            LLMError: If LLM API call fails or response cannot be parsed
        """
        pass

    @abstractmethod
    def translate_query(self, question: str) -> "QueryIntent":
        """
        Translate a natural language question into a structured graph query intent.

        Args:
            question: The user's natural language question

        Returns:
            QueryIntent: structured intent with operation type and parameters.
                         operation "unknown" means translation failed; check explanation.

        Raises:
            LLMError: If LLM API call fails or response cannot be parsed
        """
        pass
