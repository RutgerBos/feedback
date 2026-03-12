"""
Claude LLM adapter implementing LLMPort via the Anthropic API.
"""

import json
from typing import List, Dict, Any

from src.ports.llm import LLMPort, EntityExtraction
from src.ports.errors import LLMError


class ClaudeLLMAdapter(LLMPort):
    """
    Responsibilities:
    - Call Anthropic Claude API for LLM-powered extraction
    - Parse structured JSON responses into domain types
    - Handle API errors uniformly

    Collaborators:
    - anthropic.Anthropic (injected HTTP client)
    - EntityExtraction (result value object)

    Notes:
    - Client is injected for testability (no real API calls in unit tests)
    - All methods expect JSON responses from the model
    - Raises LLMError on API or parse failure
    """

    MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, client):
        """
        Args:
            client: Anthropic client instance (injected for testability)
        """
        self.client = client

    def extract_entities(self, story_text: str) -> EntityExtraction:
        """Extract entities and themes from story text via Claude."""
        prompt = (
            "Extract entities and themes from this story. "
            "Respond with JSON only: "
            '{"entities": [{"name": "...", "type": "..."}], '
            '"themes": [{"name": "...", "description": "..."}]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            return EntityExtraction(
                entities=data.get("entities", []),
                themes=data.get("themes", []),
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse entity extraction response: {e}") from e

    def extract_themes(self, story_text: str) -> List[str]:
        """Extract theme strings from story text via Claude."""
        prompt = (
            "Extract 1-5 themes from this story as descriptive phrases. "
            'Respond with JSON only: {"themes": ["theme 1", "theme 2"]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            return data.get("themes", [])
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse theme extraction response: {e}") from e

    def extract_relationships(self, story_text: str) -> List[Dict[str, Any]]:
        """Extract entity relationships from story text via Claude."""
        prompt = (
            "Extract relationships between entities in this story. "
            "Respond with JSON only: "
            '{"relationships": [{"source": "...", "target": "...", "relationship": "..."}]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            return data.get("relationships", [])
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse relationship extraction response: {e}") from e

    def _call(self, prompt: str) -> str:
        """Make a single call to the Claude API and return the text response."""
        try:
            message = self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            raise LLMError(f"Claude API call failed: {e}") from e
