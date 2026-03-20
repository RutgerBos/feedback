"""Tests for LLMPort interface."""

import pytest


def test_llm_port_is_abstract():
    """LLMPort cannot be instantiated directly."""
    from src.ports.llm import LLMPort

    with pytest.raises(TypeError, match="abstract"):
        LLMPort()


def test_llm_port_has_extract_themes_method():
    """LLMPort requires extract_themes implementation."""
    from src.ports.llm import EntityExtraction, LLMPort

    class IncompleteProvider(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_relationships(self, story_text: str) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteProvider()


def test_llm_port_has_extract_relationships_method():
    """LLMPort requires extract_relationships implementation."""
    from src.ports.llm import EntityExtraction, LLMPort

    class IncompleteProvider(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteProvider()


def test_llm_port_has_extract_sentiment_method():
    """LLMPort requires extract_sentiment implementation."""
    from src.ports.llm import EntityExtraction, LLMPort

    class IncompleteProvider(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteProvider()


def test_llm_port_has_synthesize_insights_method():
    """LLMPort requires synthesize_insights implementation."""
    from src.domain.models import SentimentAnalysis
    from src.ports.llm import EntityExtraction, LLMPort

    class IncompleteProvider(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list:
            return []

        def extract_relationships(self, story_text: str) -> list:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(emotion_markers=[], process_sentiment="neutral", outcome_sentiment="neutral")

    with pytest.raises(TypeError, match="abstract"):
        IncompleteProvider()


def test_can_implement_llm_port():
    """Can create a valid LLMPort implementation."""
    from src.domain.models import InsightContext, InsightOutput, SentimentAnalysis, SentimentSummary
    from src.ports.llm import EntityExtraction, LLMPort

    class FakeLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[])

        def extract_themes(self, story_text: str) -> list[str]:
            return []

        def extract_relationships(self, story_text: str) -> list[dict]:
            return []

        def extract_sentiment(self, story_text: str) -> SentimentAnalysis:
            return SentimentAnalysis(
                emotion_markers=[],
                process_sentiment="neutral",
                outcome_sentiment="neutral",
            )

        def synthesize_insights(self, context: InsightContext) -> InsightOutput:
            return InsightOutput(narrative="test")

    llm = FakeLLM()
    assert isinstance(llm, LLMPort)
    assert llm.extract_entities("test").entities == []
    assert llm.extract_themes("test") == []
    assert llm.extract_relationships("test") == []
    assert llm.extract_sentiment("test").process_sentiment == "neutral"
    ctx = InsightContext(
        query="q", entity_name="e", total_stories=0,
        excerpts=[], theme_counts={}, sentiment_summary=SentimentSummary(),
    )
    assert llm.synthesize_insights(ctx).narrative == "test"
