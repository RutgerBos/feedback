"""
ClusteringService: cluster stories in signifier space using GDS Louvain communities.
"""

from collections import Counter
from dataclasses import dataclass, field

from src.ports.graph import GraphPort
from src.ports.storage import StoragePort


@dataclass
class Cluster:
    """
    Responsibilities:
    - Hold one identified cluster in signifier space

    Collaborators:
    - None (value object)

    Notes:
    - center_x / center_y are the mean coordinates of member stories
      for the requested triad
    - top_themes and top_entities are ranked by frequency across members
    """

    story_ids: list[str]
    center_x: float
    center_y: float
    top_themes: list[str] = field(default_factory=list)
    top_entities: list[str] = field(default_factory=list)


@dataclass
class ClusterResult:
    """
    Responsibilities:
    - Hold the full set of clusters for one triad

    Collaborators:
    - Cluster (value object)
    """

    clusters: list[Cluster] = field(default_factory=list)


class ClusteringService:
    """
    Responsibilities:
    - Retrieve Louvain community assignments from graph
    - Load story objects from storage for coordinate and metadata
    - Compute per-cluster centroid, themes, and entities

    Collaborators:
    - GraphPort (community assignments via GDS)
    - StoragePort (story coordinate and metadata lookup)

    Notes:
    - GraphError propagates to caller
    - Stories lacking a placement for the requested triad are excluded
      from centroid calculation but still contribute themes/entities
    """

    def __init__(self, graph: GraphPort, storage: StoragePort) -> None:
        self._graph = graph
        self._storage = storage

    def cluster_by_triad(self, triad_id: str) -> ClusterResult:
        """
        Return clusters of stories grouped by Louvain community for triad_id.

        Args:
            triad_id: The triad whose proximity graph to cluster on

        Returns:
            ClusterResult with one Cluster per community

        Raises:
            GraphError: If the GDS query fails
        """
        community_pairs = self._graph.find_story_communities(triad_id)
        if not community_pairs:
            return ClusterResult()

        # Group story IDs by community
        groups: dict[int, list[str]] = {}
        for story_id, community_id in community_pairs:
            groups.setdefault(community_id, []).append(story_id)

        clusters = []
        for community_id, story_ids in sorted(groups.items()):
            stories = [self._storage.get_story(sid) for sid in story_ids]

            # Centroid: only stories with a placement for this triad
            coords = [
                p.coordinates
                for s in stories
                for p in s.triads
                if p.triad_id == triad_id
            ]
            if not coords:
                continue
            center_x = sum(c.x for c in coords) / len(coords)
            center_y = sum(c.y for c in coords) / len(coords)

            # Aggregate themes (ranked by frequency)
            theme_counts: Counter = Counter()
            for s in stories:
                for t in set(s.themes or []):
                    theme_counts[t] += 1
            top_themes = [t for t, _ in sorted(theme_counts.items(), key=lambda kv: (-kv[1], kv[0]))]

            # Aggregate entities (ranked by frequency)
            entity_counts: Counter = Counter()
            for s in stories:
                seen: set[str] = set()
                for e in s.entities or []:
                    name = e.get("name", "")
                    if name and name not in seen:
                        entity_counts[name] += 1
                        seen.add(name)
            top_entities = [e for e, _ in sorted(entity_counts.items(), key=lambda kv: (-kv[1], kv[0]))]

            clusters.append(Cluster(
                story_ids=story_ids,
                center_x=center_x,
                center_y=center_y,
                top_themes=top_themes,
                top_entities=top_entities,
            ))

        return ClusterResult(clusters=clusters)
