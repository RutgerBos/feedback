"""
Tests for triad proximity domain concepts (Story 3.4).
"""

import math

import pytest

from src.domain.models import TriadCoordinates, TriadProximity

# --- TriadCoordinates.distance_to ---

def test_distance_to_identical_coordinates_is_zero():
    coords = TriadCoordinates(x=0.3, y=0.4)
    assert coords.distance_to(coords) == pytest.approx(0.0)


def test_distance_to_basic_euclidean():
    a = TriadCoordinates(x=0.0, y=0.0)
    b = TriadCoordinates(x=0.3, y=0.4)
    assert a.distance_to(b) == pytest.approx(0.5)


def test_distance_to_is_symmetric():
    a = TriadCoordinates(x=0.1, y=0.2)
    b = TriadCoordinates(x=0.5, y=0.7)
    assert a.distance_to(b) == pytest.approx(b.distance_to(a))


# --- TriadProximity ---

def test_triad_proximity_weight_is_computed():
    p = TriadProximity(
        story_id_a="story-1",
        story_id_b="story-2",
        triad_id="workflow_nature",
        distance=0.0,
    )
    assert p.weight == pytest.approx(1.0)


def test_triad_proximity_weight_at_max_distance():
    p = TriadProximity(
        story_id_a="story-1",
        story_id_b="story-2",
        triad_id="workflow_nature",
        distance=math.sqrt(2),
    )
    assert p.weight == pytest.approx(0.0)


def test_triad_proximity_canonicalizes_ids():
    p = TriadProximity(
        story_id_a="story-z",
        story_id_b="story-a",
        triad_id="workflow_nature",
        distance=0.1,
    )
    assert p.story_id_a == "story-a"
    assert p.story_id_b == "story-z"


def test_triad_proximity_canonical_order_preserved_when_already_sorted():
    p = TriadProximity(
        story_id_a="story-a",
        story_id_b="story-z",
        triad_id="workflow_nature",
        distance=0.1,
    )
    assert p.story_id_a == "story-a"
    assert p.story_id_b == "story-z"
