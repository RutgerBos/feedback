"""LLM adapter used when enrichment is intentionally disabled."""

from src.domain.models import InsightContext, InsightOutput, QueryIntent, SentimentAnalysis
from src.ports.errors import LLMError
from src.ports.llm import EntityExtraction, LLMPort


class UnavailableLLMAdapter(LLMPort):
    """Report a configuration error through the normal LLM error contract."""

    _MESSAGE = "No LLM provider configured"

    def extract_entities(self, story_text: str) -> EntityExtraction:
        raise LLMError(self._MESSAGE)

    def extract_themes(self, story_text: str) -> list[str]:
        raise LLMError(self._MESSAGE)

    def extract_relationships(self, story_text: str) -> list[dict[str, object]]:
        raise LLMError(self._MESSAGE)

    def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
        raise LLMError(self._MESSAGE)

    def synthesize_insights(self, context: InsightContext) -> InsightOutput:
        raise LLMError(self._MESSAGE)

    def translate_query(self, question: str) -> QueryIntent:
        raise LLMError(self._MESSAGE)
