"""
Tests for ProximityCalculationService (Story 3.4).
"""


from src.domain.models import Story, TriadCoordinates, TriadPlacement, TriadProximity
from src.ports.errors import NotFoundError
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort

THRESHOLD = 0.3


def make_story(
    story_id: str = "story-1",
    processing_status: str = "processed",
    x: float = 0.3,
    y: float = 0.4,
) -> Story:
    """Make a processed story with the same coords in all three triads."""
    return Story(
        id=story_id,
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=x, y=y)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=x, y=y)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=x, y=y)),
        ],
        processing_status=processing_status,
    )


class FakeStorage(StoragePort):
    def __init__(self, stories: dict | None = None):
        self.stories: dict = stories or {}

    def save_story(self, story: Story) -> str:
        self.stories[story.id] = story
        return story.id

    def get_story(self, story_id: str) -> Story:
        if story_id not in self.stories:
            raise NotFoundError(f"Story not found: {story_id}")
        return self.stories[story_id]

    def count_stories(self, from_date=None, to_date=None) -> int:
        return len(self.stories)

    def list_stories(self, limit: int = 20, offset: int = 0, from_date=None, to_date=None) -> list:
        return list(self.stories.values())[offset:offset + limit]

    def update_story_entities(self, story_id, entities, themes, processing_status):
        pass

    def update_story_sentiment(self, story_id, sentiment, processing_status):
        pass


class FakeGraph(GraphPort):
    def __init__(self):
        self.proximity_calls: list[tuple[str, list[TriadProximity]]] = []

    def save_story_node(self, story_id, triads, timestamp):
        pass

    def save_entity_nodes(self, story_id, entities):
        pass

    def save_theme_nodes(self, story_id, themes):
        pass

    def save_proximity_relationships(self, story_id: str, pairs: list) -> None:
        self.proximity_calls.append((story_id, list(pairs)))

    def find_story_ids_by_entity(self, entity_name: str, limit: int, offset: int) -> list:
        return []

    def count_stories_by_entity(self, entity_name: str) -> int:
        return 0

    def find_themes_ranked(self, limit, from_date=None, to_date=None):
        return []

    def find_story_ids_by_theme(self, theme_name, limit, offset, from_date=None, to_date=None):
        return []

    def count_stories_by_theme(self, theme_name):
        return 0
    def find_entity_correlations(self, limit, threshold=0.0, entity_type=None):
        return []

    def find_story_ids_by_entity_pair(self, entity_a, entity_b, limit, offset=0):
        return []



# ── Test 1: no pairs when only one story ──────────────────────────────────────

def test_calculate_for_story_no_pairs_when_only_one_story():
    """No proximity pairs are created when no other stories exist."""
    from src.services.proximity import ProximityCalculationService

    story = make_story("story-1")
    storage = FakeStorage(stories={"story-1": story})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-1")

    assert graph.proximity_calls == [("story-1", [])]


# ── Test 2: creates TriadProximity per triad when close ───────────────────────

def test_calculate_for_story_creates_proximity_when_close():
    """Creates one TriadProximity per triad for story pairs within threshold."""
    from src.services.proximity import ProximityCalculationService

    story_a = make_story("story-a", x=0.1, y=0.1)
    story_b = make_story("story-b", x=0.1, y=0.2)  # distance 0.1 in each triad
    storage = FakeStorage(stories={"story-a": story_a, "story-b": story_b})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-a")

    story_id, pairs = graph.proximity_calls[0]
    assert story_id == "story-a"
    triad_ids = {p.triad_id for p in pairs}
    assert triad_ids == {"workflow_nature", "understanding_quality", "value_character"}


# ── Test 3: skips pairs above threshold ───────────────────────────────────────

def test_calculate_for_story_skips_pairs_above_threshold():
    """No pairs created when all distances exceed threshold."""
    from src.services.proximity import ProximityCalculationService

    story_a = make_story("story-a", x=0.0, y=0.0)
    story_b = make_story("story-b", x=0.5, y=0.5)  # distance ~0.707, above 0.3
    storage = FakeStorage(stories={"story-a": story_a, "story-b": story_b})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-a")

    story_id, pairs = graph.proximity_calls[0]
    assert pairs == []


# ── Test 4: skips unprocessed stories ────────────────────────────────────────

def test_calculate_for_story_skips_unprocessed_candidates():
    """Unprocessed stories are excluded from proximity calculation."""
    from src.services.proximity import ProximityCalculationService

    story_a = make_story("story-a", x=0.1, y=0.1)
    story_b = make_story("story-b", x=0.1, y=0.2, processing_status="pending")
    storage = FakeStorage(stories={"story-a": story_a, "story-b": story_b})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-a")

    story_id, pairs = graph.proximity_calls[0]
    assert pairs == []


# ── Test 5: triads matched by triad_id, not position ─────────────────────────

def test_calculate_for_story_matches_triads_by_id():
    """Triads are matched by triad_id, not list position."""
    from src.services.proximity import ProximityCalculationService

    # story_b has triads in a different order
    story_a = Story(
        id="story-a",
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.1, y=0.1)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.1, y=0.1)),
        ],
        processing_status="processed",
    )
    story_b = Story(
        id="story-b",
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.1, y=0.15)),
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.1, y=0.15)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.55)),
        ],
        processing_status="processed",
    )
    storage = FakeStorage(stories={"story-a": story_a, "story-b": story_b})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-a")

    story_id, pairs = graph.proximity_calls[0]
    # workflow_nature: (0.1,0.1)-(0.1,0.15) = 0.05 → close
    # understanding_quality: (0.5,0.5)-(0.5,0.55) = 0.05 → close
    # value_character: (0.1,0.1)-(0.1,0.15) = 0.05 → close
    triad_ids = {p.triad_id for p in pairs}
    assert "workflow_nature" in triad_ids
    assert "understanding_quality" in triad_ids


# ── Test 6: story not paired with itself ─────────────────────────────────────

def test_calculate_for_story_excludes_self():
    """The target story is not paired with itself."""
    from src.services.proximity import ProximityCalculationService

    story = make_story("story-1")
    storage = FakeStorage(stories={"story-1": story})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-1")

    story_id, pairs = graph.proximity_calls[0]
    for p in pairs:
        assert p.story_id_a != p.story_id_b


# ── Test 7: missing triad in candidate is skipped ────────────────────────────

def test_calculate_for_story_skips_missing_triad():
    """If a candidate story lacks a matching triad_id, that triad is skipped."""
    from src.services.proximity import ProximityCalculationService

    story_a = make_story("story-a", x=0.1, y=0.1)
    story_b = Story(
        id="story-b",
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.1, y=0.15)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.1, y=0.15)),
            # value_character is absent
            TriadPlacement(triad_id="other_triad", coordinates=TriadCoordinates(x=0.1, y=0.15)),
        ],
        processing_status="processed",
    )
    storage = FakeStorage(stories={"story-a": story_a, "story-b": story_b})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-a")

    story_id, pairs = graph.proximity_calls[0]
    triad_ids = {p.triad_id for p in pairs}
    assert "value_character" not in triad_ids
    assert "workflow_nature" in triad_ids


# ── Test 8: pagination across _PAGE_SIZE boundary ────────────────────────────

def test_calculate_for_story_finds_pairs_across_page_boundary():
    """Proximity pairs are found even when candidates span multiple storage pages."""
    from src.services.proximity import _PAGE_SIZE, ProximityCalculationService

    # Create _PAGE_SIZE + 1 stories so pagination is exercised
    stories = {}
    target = make_story("story-target", x=0.1, y=0.1)
    stories["story-target"] = target

    for i in range(_PAGE_SIZE):
        s = make_story(f"story-{i:04d}", x=0.1, y=0.15)  # distance 0.05 — close
        stories[s.id] = s

    storage = FakeStorage(stories=stories)
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-target")

    _, pairs = graph.proximity_calls[0]
    # All _PAGE_SIZE candidates × 3 triads should be in pairs
    assert len(pairs) == _PAGE_SIZE * 3


# ── Test 9: exact triad cardinality for reordered-triad case ─────────────────

def test_calculate_for_story_exact_triad_set_regardless_of_order():
    """Exactly the matching triads are returned, no more, no less."""
    from src.services.proximity import ProximityCalculationService

    story_a = Story(
        id="story-a",
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.1, y=0.1)),
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.5)),
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.1, y=0.1)),
        ],
        processing_status="processed",
    )
    # story_b has triads in reverse order; value_character is far away
    story_b = Story(
        id="story-b",
        story_text="CI failures blocked our deployment repeatedly this sprint. " * 3,
        triads=[
            TriadPlacement(triad_id="value_character", coordinates=TriadCoordinates(x=0.9, y=0.05)),  # far
            TriadPlacement(triad_id="understanding_quality", coordinates=TriadCoordinates(x=0.5, y=0.55)),  # close
            TriadPlacement(triad_id="workflow_nature", coordinates=TriadCoordinates(x=0.1, y=0.15)),  # close
        ],
        processing_status="processed",
    )
    storage = FakeStorage(stories={"story-a": story_a, "story-b": story_b})
    graph = FakeGraph()

    service = ProximityCalculationService(storage=storage, graph=graph, threshold=THRESHOLD)
    service.calculate_for_story("story-a")

    _, pairs = graph.proximity_calls[0]
    triad_ids = [p.triad_id for p in pairs]
    # Only the two close triads should appear, exactly once each
    assert sorted(triad_ids) == ["understanding_quality", "workflow_nature"]
