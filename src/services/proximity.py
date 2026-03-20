"""
ProximityCalculationService: compute and persist triad proximity relationships.
"""

from src.domain.models import TriadProximity
from src.ports.graph import GraphPort
from src.ports.storage import StoragePort

_PAGE_SIZE = 100


class ProximityCalculationService:
    """
    Responsibilities:
    - For a given story, compute proximity to every other processed story per triad
    - Persist qualifying pairs via GraphPort (replacing stale edges)

    Collaborators:
    - StoragePort (to page through all stories)
    - GraphPort (to write proximity relationships)

    Notes:
    - Triads are matched by triad_id, not list position
    - Candidate stories with no matching triad_id for a given triad are skipped for that triad
    - Unprocessed stories are excluded
    - Uses configurable threshold; pairs with distance >= threshold are not written
    - Paginates storage reads to avoid loading all stories at once
    """

    def __init__(
        self,
        storage: StoragePort,
        graph: GraphPort,
        threshold: float,
    ) -> None:
        self._storage = storage
        self._graph = graph
        self._threshold = threshold

    def calculate_for_story(self, story_id: str) -> None:
        """Replace proximity relationships for story_id.

        Reads the target story, pages through all other processed stories,
        computes per-triad Euclidean distances, and writes qualifying pairs.
        """
        target = self._storage.get_story(story_id)
        target_coords = {p.triad_id: p.coordinates for p in target.triads}

        pairs: list[TriadProximity] = []

        offset = 0
        while True:
            page = self._storage.list_stories(limit=_PAGE_SIZE, offset=offset)
            if not page:
                break
            for candidate in page:
                if candidate.id == story_id:
                    continue
                if candidate.processing_status != "processed":
                    continue
                candidate_coords = {p.triad_id: p.coordinates for p in candidate.triads}
                for triad_id, tc in target_coords.items():
                    cc = candidate_coords.get(triad_id)
                    if cc is None:
                        continue
                    dist = tc.distance_to(cc)
                    if dist < self._threshold:
                        pairs.append(
                            TriadProximity(
                                story_id_a=story_id,
                                story_id_b=candidate.id,
                                triad_id=triad_id,
                                distance=dist,
                            )
                        )
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE

        self._graph.save_proximity_relationships(story_id=story_id, pairs=pairs)
