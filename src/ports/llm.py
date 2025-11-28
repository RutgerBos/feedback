"""
LLMPort interface for entity extraction.

This port defines the contract for extracting entities and themes from stories,
independent of the actual LLM provider (Claude, OpenAI, local model, etc).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class EntityExtraction:
    """
    Responsibilities:
    - Hold extracted entities and themes from story text
    - Provide structured output from LLM processing

    Collaborators:
    - None (value object)

    Notes:
    - Simple data holder for LLM extraction results
    - Structure will evolve as we understand extraction needs
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
        Extract entities and themes from story text.

        Args:
            story_text: The narrative text to analyze

        Returns:
            EntityExtraction: Structured extraction results

        Raises:
            LLMError: If LLM API call fails
            ValidationError: If LLM response cannot be parsed
        """
        pass
