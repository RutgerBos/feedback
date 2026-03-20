"""Tests for SentimentAnalysis domain model and Story.sentiment field."""

import pytest

from src.domain.models import SentimentAnalysis, Story, TriadCoordinates, TriadPlacement


def make_story(story_id: str = "s-1") -> Story:
    return Story(
        id=story_id,
        story_text="I had to restart the CI pipeline three times today due to flaky tests. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.3, y=0.6)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.4)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.2, y=0.7)),
        ],
    )


# ── Test 1: can create SentimentAnalysis ──────────────────────────────────────

def test_sentiment_analysis_can_be_created():
    """SentimentAnalysis holds emotion_markers, process_sentiment, outcome_sentiment."""
    sa = SentimentAnalysis(
        emotion_markers=["frustration", "relief"],
        process_sentiment="negative",
        outcome_sentiment="positive",
    )

    assert sa.emotion_markers == ["frustration", "relief"]
    assert sa.process_sentiment == "negative"
    assert sa.outcome_sentiment == "positive"


# ── Test 2: emotion_markers is a list of strings ──────────────────────────────

def test_sentiment_analysis_emotion_markers_is_list():
    """emotion_markers accepts a list of strings."""
    sa = SentimentAnalysis(
        emotion_markers=["confusion", "anxiety", "satisfaction"],
        process_sentiment="mixed",
        outcome_sentiment="positive",
    )

    assert isinstance(sa.emotion_markers, list)
    assert all(isinstance(m, str) for m in sa.emotion_markers)


# ── Test 3: empty emotion_markers is valid ────────────────────────────────────

def test_sentiment_analysis_empty_emotion_markers():
    """emotion_markers may be an empty list."""
    sa = SentimentAnalysis(
        emotion_markers=[],
        process_sentiment="neutral",
        outcome_sentiment="neutral",
    )

    assert sa.emotion_markers == []


# ── Test 4: immutable (frozen) ────────────────────────────────────────────────

def test_sentiment_analysis_is_immutable():
    """SentimentAnalysis is a frozen value object."""
    sa = SentimentAnalysis(
        emotion_markers=["frustration"],
        process_sentiment="negative",
        outcome_sentiment="negative",
    )

    with pytest.raises(Exception):
        sa.process_sentiment = "positive"  # type: ignore[misc]


# ── Story.sentiment field ──────────────────────────────────────────────────────

def test_story_sentiment_defaults_to_none():
    """Story.sentiment is None by default."""
    story = make_story()

    assert story.sentiment is None


def test_story_sentiment_can_be_set():
    """Story can be created with a SentimentAnalysis value."""
    sa = SentimentAnalysis(
        emotion_markers=["frustration"],
        process_sentiment="negative",
        outcome_sentiment="positive",
    )
    story = make_story()
    story_with_sentiment = story.model_copy(update={"sentiment": sa})

    assert story_with_sentiment.sentiment is not None
    assert story_with_sentiment.sentiment.process_sentiment == "negative"
