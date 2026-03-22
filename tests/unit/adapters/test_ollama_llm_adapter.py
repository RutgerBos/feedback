"""Tests for OllamaLLMAdapter."""

import json

import pytest

from src.ports.llm import EntityExtraction, LLMPort


def make_fake_http_client(response_text: str):
    """Create a fake HTTP client that returns a canned JSON response."""

    class FakeResponse:
        def raise_for_status(self):
            pass  # success — no-op

        def json(self):
            return {"response": response_text}

    class FakeClient:
        def post(self, url, **kwargs):
            return FakeResponse()

    return FakeClient()


def test_ollama_adapter_implements_llm_port():
    """OllamaLLMAdapter is a valid LLMPort implementation."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    client = make_fake_http_client('{"entities": [], "themes": []}')
    adapter = OllamaLLMAdapter(http_client=client)

    assert isinstance(adapter, LLMPort)


def test_ollama_adapter_extract_entities_returns_entity_extraction():
    """extract_entities parses ollama JSON response into EntityExtraction."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({
        "entities": [{"name": "CI pipeline", "type": "tool"}],
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_entities("I had to restart the CI pipeline.")

    assert isinstance(result, EntityExtraction)
    assert result.entities[0]["name"] == "CI pipeline"


def test_ollama_adapter_extract_themes_returns_list_of_strings():
    """extract_themes parses ollama JSON response into list of strings."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({"themes": ["tooling reliability", "developer friction"]})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_themes("CI keeps failing on us.")

    assert result == ["tooling reliability", "developer friction"]


def test_ollama_adapter_raises_on_http_error():
    """extract_entities raises LLMError when the HTTP response indicates an error."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    class ErrorResponse:
        def raise_for_status(self):
            raise Exception("500 Server Error")
        def json(self):
            return {"error": "model not found"}

    class ErrorClient:
        def post(self, url, **kwargs):
            return ErrorResponse()

    adapter = OllamaLLMAdapter(http_client=ErrorClient())

    with pytest.raises(LLMError):
        adapter.extract_entities("some story text here")


def test_ollama_adapter_extract_entities_raises_on_missing_key():
    """extract_entities raises LLMError when expected keys are absent."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    adapter = OllamaLLMAdapter(http_client=make_fake_http_client("{}"))

    with pytest.raises(LLMError):
        adapter.extract_entities("some story text here")


def test_ollama_adapter_extract_entities_raises_on_bad_shape():
    """extract_entities raises LLMError when response has wrong shape."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({"entities": "not-a-list", "themes": []})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_entities("some story text here")


def test_ollama_adapter_extract_themes_raises_on_bad_shape():
    """extract_themes raises LLMError when themes is not a list."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({"themes": "not-a-list"})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_themes("some story text here")


def test_ollama_adapter_extract_themes_raises_on_non_string_elements():
    """extract_themes raises LLMError when any element is not a string.

    Story.themes is List[str]; non-string elements would cause a Pydantic
    ValidationError on readback. The adapter must catch this at the boundary.
    """
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({"themes": ["valid theme", 42, {"name": "oops"}]})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_themes("some story text here")


def test_ollama_adapter_extract_relationships_returns_list_of_dicts():
    """extract_relationships parses ollama JSON response into list of dicts."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({
        "relationships": [{"source": "CI", "target": "deploy", "relationship": "BLOCKS"}]
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_relationships("CI failures blocked deploys.")

    assert result[0]["source"] == "CI"
    assert result[0]["relationship"] == "BLOCKS"


def test_ollama_adapter_extract_sentiment_returns_sentiment_analysis():
    """extract_sentiment parses ollama JSON response into SentimentAnalysis."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.domain.models import SentimentAnalysis

    response = json.dumps({
        "emotion_markers": ["frustration", "relief"],
        "process_sentiment": "negative",
        "outcome_sentiment": "positive",
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_sentiment("I struggled with CI but eventually fixed it.")

    assert isinstance(result, SentimentAnalysis)
    assert result.emotion_markers == ["frustration", "relief"]
    assert result.process_sentiment == "negative"
    assert result.outcome_sentiment == "positive"


def test_ollama_adapter_extract_sentiment_raises_on_missing_key():
    """extract_sentiment raises LLMError when expected keys are absent."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    adapter = OllamaLLMAdapter(http_client=make_fake_http_client("{}"))

    with pytest.raises(LLMError):
        adapter.extract_sentiment("some story text here")


def test_ollama_adapter_extract_sentiment_raises_on_non_string_emotion_markers():
    """extract_sentiment raises LLMError when emotion_markers contains non-strings."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({
        "emotion_markers": ["frustration", 42],
        "process_sentiment": "negative",
        "outcome_sentiment": "positive",
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError):
        adapter.extract_sentiment("some story text here")


def test_ollama_adapter_extract_sentiment_handles_empty_emotion_markers():
    """extract_sentiment accepts empty emotion_markers list."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.domain.models import SentimentAnalysis

    response = json.dumps({
        "emotion_markers": [],
        "process_sentiment": "neutral",
        "outcome_sentiment": "neutral",
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.extract_sentiment("A routine day with nothing notable.")

    assert isinstance(result, SentimentAnalysis)
    assert result.emotion_markers == []
    assert result.process_sentiment == "neutral"


def test_ollama_adapter_extract_sentiment_raises_llmerror_on_invalid_label():
    """extract_sentiment wraps an unrecognised sentiment label as LLMError, not ValidationError."""
    import json
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    bad_response = json.dumps({
        "emotion_markers": [],
        "process_sentiment": "cautious",
        "outcome_sentiment": "neutral",
    })
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(bad_response))

    with pytest.raises(LLMError, match="cautious"):
        adapter.extract_sentiment("some story text here")


# ── synthesize_insights ────────────────────────────────────────────────────────


def make_insight_context():
    from src.domain.models import InsightContext, SentimentSummary, StoryExcerpt
    return InsightContext(
        query="Why do CI stories cluster here?",
        entity_name="CI pipeline",
        total_stories=1,
        excerpts=[StoryExcerpt(story_id="s1", text_excerpt="Pipeline broke.", triad_positions={})],
        theme_counts={"automation friction": 1},
        sentiment_summary=SentimentSummary(negative_process=1),
    )


def test_ollama_adapter_synthesize_insights_returns_insight_output():
    """synthesize_insights parses narrative and caveats from Ollama response."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.domain.models import InsightOutput

    response = json.dumps({"narrative": "CI issues cluster here.", "caveats": ["Small sample."]})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.synthesize_insights(make_insight_context())

    assert isinstance(result, InsightOutput)
    assert result.narrative == "CI issues cluster here."
    assert result.caveats == ["Small sample."]


def test_ollama_adapter_synthesize_insights_raises_on_missing_narrative_key():
    """synthesize_insights raises LLMError when narrative key is absent."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    response = json.dumps({"caveats": ["Caveat only."]})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))
    with pytest.raises(LLMError, match="narrative"):
        adapter.synthesize_insights(make_insight_context())


def test_ollama_adapter_synthesize_insights_raises_on_bad_json():
    """synthesize_insights raises LLMError when response is not valid JSON."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    adapter = OllamaLLMAdapter(http_client=make_fake_http_client("not json"))
    with pytest.raises(LLMError):
        adapter.synthesize_insights(make_insight_context())


# ── translate_query tests ─────────────────────────────────────────────────────


def test_ollama_adapter_translate_query_returns_entity_intent():
    """translate_query parses by_entity response into QueryIntent."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.domain.models import QueryIntent

    response = json.dumps({"operation": "by_entity", "entity": "CI pipeline"})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.translate_query("What issues exist with the CI pipeline?")

    assert isinstance(result, QueryIntent)
    assert result.operation == "by_entity"
    assert result.entity == "CI pipeline"


def test_ollama_adapter_translate_query_returns_theme_intent():
    """translate_query parses by_theme response into QueryIntent."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    response = json.dumps({"operation": "by_theme", "theme": "automation friction"})
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(response))

    result = adapter.translate_query("Tell me about automation friction.")

    assert result.operation == "by_theme"
    assert result.theme == "automation friction"


def test_ollama_adapter_translate_query_strips_code_fences():
    """translate_query accepts JSON wrapped in markdown code fences."""
    from src.adapters.ollama_llm import OllamaLLMAdapter

    fenced = "```json\n" + json.dumps({"operation": "by_entity", "entity": "CI"}) + "\n```"
    adapter = OllamaLLMAdapter(http_client=make_fake_http_client(fenced))

    result = adapter.translate_query("CI issues?")

    assert result.operation == "by_entity"
    assert result.entity == "CI"


def test_ollama_adapter_translate_query_raises_on_bad_json():
    """translate_query raises LLMError when model returns non-JSON."""
    from src.adapters.ollama_llm import OllamaLLMAdapter
    from src.ports.errors import LLMError

    adapter = OllamaLLMAdapter(http_client=make_fake_http_client("not json"))

    with pytest.raises(LLMError):
        adapter.translate_query("Any question")
