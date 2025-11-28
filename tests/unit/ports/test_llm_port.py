"""Tests for LLMPort interface."""

import pytest


def test_llm_port_is_abstract():
    """LLMPort cannot be instantiated directly."""
    from src.ports.llm import LLMPort

    with pytest.raises(TypeError, match="abstract"):
        LLMPort()


def test_can_implement_llm_port():
    """Can create a valid LLMPort implementation."""
    from src.ports.llm import LLMPort, EntityExtraction

    class FakeLLM(LLMPort):
        def extract_entities(self, story_text: str) -> EntityExtraction:
            return EntityExtraction(entities=[], themes=[])

    llm = FakeLLM()
    assert llm is not None
    assert isinstance(llm, LLMPort)

    result = llm.extract_entities("test story")
    assert result.entities == []
    assert result.themes == []
