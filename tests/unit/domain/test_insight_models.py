"""Tests for insight synthesis domain models."""

from src.domain.models import InsightContext, InsightOutput, SentimentSummary, StoryExcerpt


def test_story_excerpt_holds_id_text_and_positions():
    excerpt = StoryExcerpt(
        story_id="s1",
        text_excerpt="CI pipeline kept failing.",
        triad_positions={"workflow": {"x": 0.3, "y": 0.6}},
    )
    assert excerpt.story_id == "s1"
    assert excerpt.text_excerpt == "CI pipeline kept failing."
    assert excerpt.triad_positions == {"workflow": {"x": 0.3, "y": 0.6}}


def test_sentiment_summary_defaults_to_zero():
    summary = SentimentSummary()
    assert summary.positive_process == 0
    assert summary.neutral_outcome == 0


def test_sentiment_summary_holds_counts():
    summary = SentimentSummary(positive_process=3, negative_outcome=2)
    assert summary.positive_process == 3
    assert summary.negative_outcome == 2
    assert summary.neutral_process == 0


def test_insight_context_holds_all_fields():
    excerpt = StoryExcerpt(story_id="s1", text_excerpt="text", triad_positions={})
    summary = SentimentSummary(positive_process=1)
    ctx = InsightContext(
        query="Why do CI stories cluster here?",
        entity_name="CI pipeline",
        total_stories=5,
        excerpts=[excerpt],
        theme_counts={"automation": 3, "friction": 2},
        sentiment_summary=summary,
    )
    assert ctx.query == "Why do CI stories cluster here?"
    assert ctx.total_stories == 5
    assert ctx.theme_counts["automation"] == 3


def test_insight_output_holds_narrative_and_caveats():
    output = InsightOutput(narrative="Stories show frustration.", caveats=["Small sample."])
    assert output.narrative == "Stories show frustration."
    assert output.caveats == ["Small sample."]


def test_insight_output_caveats_default_empty():
    output = InsightOutput(narrative="Some insight.")
    assert output.caveats == []
