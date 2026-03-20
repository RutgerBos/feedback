"""
Ollama LLM adapter implementing LLMPort via a local ollama instance.
"""

import json
from typing import Any

from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis
from src.ports.errors import LLMError
from src.ports.llm import EntityExtraction, LLMPort


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
        """Extract entities from story text via ollama."""
        prompt = (
            "Extract entities from this story. "
            "Respond with JSON only: "
            '{"entities": [{"name": "...", "type": "..."}]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            return EntityExtraction(entities=self._require_list(data, "entities"))
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse entity extraction response: {e}") from e

    def extract_themes(self, story_text: str) -> list[str]:
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

    def extract_relationships(self, story_text: str) -> list[dict[str, Any]]:
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

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        """Extract sentiment and emotional tone from story text via ollama."""
        prompt = (
            "Analyze the emotional tone of this story. "
            "Identify specific emotion markers (e.g. frustration, relief, confusion), "
            "the overall sentiment about the process experienced, "
            "and the overall sentiment about the outcome achieved. "
            "Respond with JSON only: "
            '{"emotion_markers": ["..."], "process_sentiment": "...", "outcome_sentiment": "..."}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            emotion_markers = self._require_list(data, "emotion_markers")
            if not all(isinstance(m, str) for m in emotion_markers):
                raise LLMError("Expected all emotion_markers to be strings")
            process_sentiment = data["process_sentiment"]
            outcome_sentiment = data["outcome_sentiment"]
            if not isinstance(process_sentiment, str) or not isinstance(outcome_sentiment, str):
                raise LLMError("process_sentiment and outcome_sentiment must be strings")
            return SentimentAnalysis(
                emotion_markers=emotion_markers,
                process_sentiment=process_sentiment,
                outcome_sentiment=outcome_sentiment,
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse sentiment extraction response: {e}") from e

    def synthesize_insights(self, context: InsightContext) -> InsightOutput:
        """Synthesize a narrative insight from structured pattern evidence via ollama."""
        excerpt_lines = "\n".join(
            f'- [{e.story_id}] "{e.text_excerpt}"'
            for e in context.excerpts
        )
        theme_lines = "\n".join(
            f"  {theme}: {count} stories" for theme, count in sorted(
                context.theme_counts.items(), key=lambda x: -x[1]
            )
        )
        s = context.sentiment_summary
        sentiment_line = (
            f"Process — positive: {s.positive_process}, negative: {s.negative_process}, neutral: {s.neutral_process}; "
            f"Outcome — positive: {s.positive_outcome}, negative: {s.negative_outcome}, neutral: {s.neutral_outcome}"
        )
        prompt = (
            f"You are analyzing feedback stories about '{context.entity_name}'.\n"
            f"User question: {context.query}\n\n"
            f"Total matching stories: {context.total_stories} "
            f"(showing {len(context.excerpts)} excerpts)\n\n"
            f"Story excerpts:\n{excerpt_lines}\n\n"
            f"Theme distribution:\n{theme_lines if theme_lines else '  (no themes extracted)'}\n\n"
            f"Sentiment summary: {sentiment_line}\n\n"
            "Write a clear, concise narrative (3-5 sentences) explaining what patterns emerge "
            "from these stories. Include any important caveats about data quality or sample size.\n"
            'Respond with JSON only: {"narrative": "...", "caveats": ["..."]}'
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            narrative = data.get("narrative", "")
            caveats = data.get("caveats", [])
            if not isinstance(narrative, str):
                raise LLMError("Expected 'narrative' to be a string")
            if not isinstance(caveats, list) or not all(isinstance(c, str) for c in caveats):
                raise LLMError("Expected 'caveats' to be a list of strings")
            return InsightOutput(narrative=narrative, caveats=caveats)
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse insight synthesis response: {e}") from e

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
