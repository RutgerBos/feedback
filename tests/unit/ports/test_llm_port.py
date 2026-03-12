"""Tests for LLMPort interface."""

import pytest


def test_llm_port_is_abstract():
    """LLMPort cannot be instantiated directly."""
    from src.ports.llm import LLMPort

    with pytest.raises(TypeError, match="abstract"):
        LLMPort()


def test_llm_port_has_extract_themes_method():
    """LLMPort requires extract_themes implementation."""
    from src.ports.llm import LLMPort, EntityExtraction

    class IncompleteProvider(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[], themes=[])

        def extract_relationships(self, story_text: str) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteProvider()


def test_llm_port_has_extract_relationships_method():
    """LLMPort requires extract_relationships implementation."""
    from src.ports.llm import LLMPort, EntityExtraction

    class IncompleteProvider(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[], themes=[])

        def extract_themes(self, story_text: str) -> list:
            return []

    with pytest.raises(TypeError, match="abstract"):
        IncompleteProvider()


def test_can_implement_llm_port():
    """Can create a valid LLMPort implementation."""
    from src.ports.llm import LLMPort, EntityExtraction

    class FakeLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[], themes=[])

        def extract_themes(self, story_text: str) -> list[str]:
            return []

        def extract_relationships(self, story_text: str) -> list[dict]:
            return []

    llm = FakeLLM()
    assert isinstance(llm, LLMPort)
    assert llm.extract_entities("test") .entities == []
    assert llm.extract_themes("test") == []
    assert llm.extract_relationships("test") == []
