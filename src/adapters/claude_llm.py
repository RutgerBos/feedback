"""
Claude LLM adapter implementing LLMPort via the Anthropic API.
"""

import json
from typing import Any

from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis
from src.ports.errors import LLMError
from src.ports.llm import EntityExtraction, LLMPort


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

    def __init__(self, client: Any) -> None:
        """
        Args:
            client: Anthropic client instance (injected for testability)
        """
        self.client = client

    def extract_entities(self, story_text: str) -> EntityExtraction:
        """Extract entities from story text via Claude."""
        prompt = (
            "Extract entities from this story. "
            "Respond with JSON only: "
            '{"entities": [{"name": "...", "type": "..."}]}\n\n'
            f"Story: {story_text}"
        )
        raw = self._call(prompt)
        try:
            data = json.loads(raw)
            entities = self._require_list(data, "entities")
            return EntityExtraction(entities=entities)
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse entity extraction response: {e}") from e

    def extract_themes(self, story_text: str) -> list[str]:
        """Extract theme strings from story text via Claude."""
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
            return self._require_list(data, "relationships")
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"Failed to parse relationship extraction response: {e}") from e

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        """Extract sentiment and emotional tone from story text via Claude."""
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
        """Synthesize a narrative insight from structured pattern evidence via Claude."""
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
        """Make a single call to the Claude API and return the text response."""
        try:
            message = self.client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return str(message.content[0].text)
        except Exception as e:
            raise LLMError(f"Claude API call failed: {e}") from e
