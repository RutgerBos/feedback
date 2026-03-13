"""
Ollama LLM adapter implementing LLMPort via a local ollama instance.
"""

import json
from typing import List, Dict, Any

from src.ports.llm import LLMPort, EntityExtraction
from src.ports.errors import LLMError


class OllamaLLMAdapter(LLMPort):
    """
    Responsibilities:
    - Call a local ollama server for LLM-powered extraction
    - Parse structured JSON responses into domain types
    - Handle HTTP and parse errors uniformly

    Collaborators:
    - httpx.Client (injected HTTP client)
    - EntityExtraction (result value object)

    Notes:
    - http_client is injected for testability (no real HTTP calls in unit tests)
    - Defaults to localhost:11434 (standard ollama port)
    - Raises LLMError on HTTP or parse failure
    """

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "llama3"

    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL, http_client: Any = None) -> None:
        """
        Args:
            base_url: Base URL of the ollama server
            model: Model name to use for generation
            http_client: HTTP client instance (injected for testability)
        """
        self.base_url = base_url
        self.model = model
        self._http_client = http_client

    @property
    def http_client(self) -> Any:
        if self._http_client is None:
            import httpx
            self._http_client = httpx.Client()
        return self._http_client

    def extract_entities(self, story_text: str) -> EntityExtraction:
        """Extract entities and themes from story text via ollama."""
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
                entities=self._require_list(data, "entities"),
                themes=self._require_list(data, "themes"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse entity extraction response: {e}") from e

    def extract_themes(self, story_text: str) -> List[str]:
        """Extract theme strings from story text via ollama."""
        prompt = (
            "Extract 1-5 themes from this story as descriptive phrases. "
            'Respond with JSON only: {"themes": ["theme 1", "theme 2"]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            themes = self._require_list(data, "themes")
            if not all(isinstance(t, str) for t in themes):
                raise LLMError("Expected all theme elements to be strings")
            return themes
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse theme extraction response: {e}") from e

    def extract_relationships(self, story_text: str) -> List[Dict[str, Any]]:
        """Extract entity relationships from story text via ollama."""
        prompt = (
            "Extract relationships between entities in this story. "
            "Respond with JSON only: "
            '{"relationships": [{"source": "...", "target": "...", "relationship": "..."}]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            return self._require_list(data, "relationships")
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse relationship extraction response: {e}") from e

    def _require_list(self, data: dict, key: str) -> list:
        """Extract a list value from parsed JSON, raising LLMError if missing or not a list."""
        if key not in data:
            raise LLMError(f"Missing required key '{key}' in LLM response")
        value = data[key]
        if not isinstance(value, list):
            raise LLMError(f"Expected '{key}' to be a list, got {type(value).__name__}")
        return value

    def _call(self, prompt: str) -> str:
        """POST to the ollama /api/generate endpoint and return the response text."""
        try:
            response = self.http_client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return str(response.json()["response"])
        except Exception as e:
            raise LLMError(f"Ollama API call failed: {e}") from e
