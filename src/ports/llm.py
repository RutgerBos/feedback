"""
LLMPort interface for story analysis.

This port defines the contract for extracting entities, themes, and relationships
from stories, independent of the actual LLM provider (Claude, OpenAI, local model, etc).
EntityExtraction holds entity results only; themes are returned separately by extract_themes().
"""

from abc import ABC, abstractmethod
from typing import Any


class EntityExtraction:
    """
    Responsibilities:
    - Hold extracted entities from an extraction pass

    Collaborators:
    - None (value object)

    Notes:
    - Used by extract_entities() for entity-only extraction
    - entities: [{"name": "...", "type": "..."}]
    - Themes are extracted separately via extract_themes()
    """

    def __init__(self, entities: list[dict[str, Any]]):
        self.entities = entities


class LLMPort(ABC):
    """
    Responsibilities:
    - Extract entities from story text
    - Extract themes from story text
    - Provide LLM-powered analysis of narratives

    Collaborators:
    - EntityExtraction (result object)

    Notes:
    - No knowledge of LLM provider (Claude, OpenAI, local, etc)
    - Returns structured data, not raw LLM responses
    - Interface designed for current needs (Story processing)
    - Will expand with additional analysis methods as needed
    - May raise LLMError for API failures
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
