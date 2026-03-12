"""
LLMPort interface for entity extraction.

This port defines the contract for extracting entities and themes from stories,
independent of the actual LLM provider (Claude, OpenAI, local model, etc).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple


class EntityExtraction:
    """
    Responsibilities:
    - Hold extracted entities and rich theme objects from a combined extraction

    Collaborators:
    - None (value object)

    Notes:
    - Used by extract_entities() for a combined extraction pass
    - entities: [{"name": "...", "type": "..."}]
    - themes: [{"name": "...", "description": "..."}]  (rich objects, not plain strings)
    - For plain theme strings use extract_themes() instead
    """

    def __init__(self, entities: List[Dict[str, Any]], themes: List[Dict[str, Any]]):
        self.entities = entities
        self.themes = themes


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
    def extract_themes(self, story_text: str) -> List[str]:
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
    def extract_relationships(self, story_text: str) -> List[Dict[str, Any]]:
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
