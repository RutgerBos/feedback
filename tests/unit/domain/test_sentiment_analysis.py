"""Tests for SentimentAnalysis domain model."""

import pytest

from src.domain.models import SentimentAnalysis


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
