"""Deterministic anomaly detection from graph structure and story metadata."""

from dataclasses import dataclass, field

from src.domain.models import Story
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort

_PAGE_SIZE = 100
_MIN_IQR_SAMPLE = 4
_PROFILE_MISMATCH_THRESHOLD = 0.75


@dataclass(frozen=True)
class AnomalyReason:
    """
    Responsibilities:
    - Represent one explainable signal that makes a story unusual

    Collaborators:
    - None
    """

    kind: str
    score: float
    explanation: str


@dataclass(frozen=True)
class StoryAnomaly:
    """
    Responsibilities:
    - Represent a story's combined anomaly score and evidence

    Collaborators:
    - AnomalyReason
    """

    story_id: str
    score: float
    reasons: list[AnomalyReason] = field(default_factory=list)


@dataclass(frozen=True)
class AnomalyResult:
    """
    Responsibilities:
    - Represent a ranked set of story anomalies

    Collaborators:
    - StoryAnomaly
    """

    anomalies: list[StoryAnomaly] = field(default_factory=list)


class AnomalyDetectionService:
    """
    Responsibilities:
    - Identify unusual processed stories from structural and signifier evidence
    - Rank anomalies with deterministic, explainable reasons

    Collaborators:
    - GraphPort
    - StoragePort
    """

    def __init__(self, graph: GraphPort, storage: StoragePort) -> None:
        self._graph = graph
        self._storage = storage

    def find_anomalies(self, limit: int) -> AnomalyResult:
        """Return at most ``limit`` anomalous stories in stable rank order."""
        stories = self._load_processed_stories()
        neighbourhoods = {
            story_id: set(neighbours)
            for story_id, neighbours in self._graph.find_story_neighbourhoods()
        }
        reasons: dict[str, list[AnomalyReason]] = {story_id: [] for story_id in stories}

        self._add_graph_reasons(stories, neighbourhoods, reasons)
        self._add_coordinate_reasons(stories, reasons)
        self._add_profile_reasons(stories, neighbourhoods, reasons)

        anomalies = []
        for story_id, story_reasons in reasons.items():
            if not story_reasons:
                continue
            ordered_reasons = sorted(
                story_reasons,
                key=lambda reason: (-reason.score, reason.kind, reason.explanation),
            )
            anomalies.append(
                StoryAnomaly(
                    story_id=story_id,
                    score=max(reason.score for reason in ordered_reasons),
                    reasons=ordered_reasons,
                )
            )
        anomalies.sort(key=lambda anomaly: (-anomaly.score, anomaly.story_id))
        return AnomalyResult(anomalies=anomalies[:limit])

    def _load_processed_stories(self) -> dict[str, Story]:
        stories: dict[str, Story] = {}
        offset = 0
        while True:
            page = self._storage.list_stories(limit=_PAGE_SIZE, offset=offset)
            for story in page:
                if story.processing_status == "processed":
                    stories[story.id] = story
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return stories

    @staticmethod
    def _add_graph_reasons(
        stories: dict[str, Story],
        neighbourhoods: dict[str, set[str]],
        reasons: dict[str, list[AnomalyReason]],
    ) -> None:
        degrees = {story_id: len(neighbourhoods.get(story_id, set())) for story_id in stories}
        for story_id, degree in degrees.items():
            if degree == 0:
                reasons[story_id].append(
                    AnomalyReason("disconnected", 1.0, "Story has no proximity neighbours.")
                )

        if len(degrees) < _MIN_IQR_SAMPLE:
            return
        values = [degree for degree in degrees.values() if degree > 0]
        if len(values) < _MIN_IQR_SAMPLE:
            return
        q1 = _percentile(values, 0.25)
        q3 = _percentile(values, 0.75)
        iqr = q3 - q1
        if iqr == 0:
            return
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        observed_range = max(values) - min(values)
        if observed_range == 0:
            return
        for story_id, degree in degrees.items():
            if degree == 0:
                continue
            if degree < lower:
                score = min(1.0, (lower - degree) / observed_range)
                reasons[story_id].append(
                    AnomalyReason(
                        "low_degree",
                        score,
                        f"Story has unusually few proximity neighbours ({degree}).",
                    )
                )
            elif degree > upper:
                score = min(1.0, (degree - upper) / observed_range)
                reasons[story_id].append(
                    AnomalyReason(
                        "high_degree",
                        score,
                        f"Story has unusually many proximity neighbours ({degree}).",
                    )
                )

    @staticmethod
    def _add_coordinate_reasons(
        stories: dict[str, Story], reasons: dict[str, list[AnomalyReason]]
    ) -> None:
        axes: dict[tuple[str, str], list[tuple[str, float]]] = {}
        for story in stories.values():
            responses = story.signification.responses if story.signification else []
            for response in responses:
                axes.setdefault((response.signifier_id, "x"), []).append(
                    (story.id, response.coordinates.x)
                )
                axes.setdefault((response.signifier_id, "y"), []).append(
                    (story.id, response.coordinates.y)
                )

        for (signifier_id, axis), observations in axes.items():
            if len(observations) < _MIN_IQR_SAMPLE:
                continue
            values = [value for _, value in observations]
            q1 = _percentile(values, 0.25)
            q3 = _percentile(values, 0.75)
            iqr = q3 - q1
            observed_range = max(values) - min(values)
            if iqr == 0 or observed_range == 0:
                continue
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            for story_id, value in observations:
                distance = lower - value if value < lower else value - upper if value > upper else 0
                if distance <= 0:
                    continue
                reasons[story_id].append(
                    AnomalyReason(
                        "coordinate_outlier",
                        min(1.0, distance / observed_range),
                        f"{signifier_id} {axis}-coordinate is outside the dataset's IQR fence.",
                    )
                )

    @staticmethod
    def _add_profile_reasons(
        stories: dict[str, Story],
        neighbourhoods: dict[str, set[str]],
        reasons: dict[str, list[AnomalyReason]],
    ) -> None:
        profiles = {story_id: _profile(story) for story_id, story in stories.items()}
        for story_id, profile in profiles.items():
            if not profile:
                continue
            similarities = []
            for neighbour_id in neighbourhoods.get(story_id, set()):
                neighbour_profile = profiles.get(neighbour_id)
                if not neighbour_profile:
                    continue
                similarities.append(
                    len(profile & neighbour_profile) / len(profile | neighbour_profile)
                )
            if not similarities:
                continue
            mismatch = 1.0 - sum(similarities) / len(similarities)
            if mismatch > _PROFILE_MISMATCH_THRESHOLD:
                reasons[story_id].append(
                    AnomalyReason(
                        "profile_mismatch",
                        mismatch,
                        f"Theme/entity profile differs by {mismatch:.0%} from "
                        f"{len(similarities)} proximity neighbour(s).",
                    )
                )


def _profile(story: Story) -> set[str]:
    values = [*story.themes, *(entity.get("name", "") for entity in story.entities)]
    return {normalized for value in values if (normalized := " ".join(value.split()).lower())}


def _percentile(values: list[int] | list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index
    return ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight
