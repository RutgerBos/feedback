"""
InsightSynthesisService: assembles evidence from graph + storage and asks
the LLM to synthesize a narrative explanation.
"""

from dataclasses import dataclass, field

from src.domain.models import (
    InsightContext,
    InsightOutput,
    SentimentSummary,
    StoryExcerpt,
)
from src.ports.graph import GraphPort
from src.ports.llm import LLMPort
from src.ports.storage import StoragePort

_MAX_STORIES = 20
_EXCERPT_LEN = 300


@dataclass
class InsightResponse:
    """
    Responsibilities:
    - Hold synthesis result: narrative, caveats, and supporting evidence

    Collaborators:
    - StoryExcerpt (value object)
    - SentimentSummary (value object)

    Notes:
    - narrative is empty string when no stories match (LLM not called)
    - story_count is the full graph match count, not the sample size
    """

    narrative: str
    story_count: int
    caveats: list[str] = field(default_factory=list)
    theme_counts: dict[str, int] = field(default_factory=dict)
    sentiment_summary: SentimentSummary = field(default_factory=SentimentSummary)
    excerpts: list[StoryExcerpt] = field(default_factory=list)


class InsightSynthesisService:
    """
    Responsibilities:
    - Fetch story IDs for an entity from the graph
    - Load stories from storage and compute theme/sentiment statistics
    - Build a bounded InsightContext and call the LLM
    - Return InsightResponse with narrative and supporting evidence

    Collaborators:
    - GraphPort (to query story IDs and total count)
    - StoragePort (to load full story objects)
    - LLMPort (to synthesize the narrative)

    Notes:
    - MVP scope: entity-name query only (free-text pattern retrieval not yet supported)
    - Capped at 20 stories; excerpts are truncated to 300 chars
    - LLMError propagates to the caller
    - When no stories match, returns empty narrative without calling the LLM
    """

    def __init__(
        self, graph: GraphPort, storage: StoragePort, llm: LLMPort
    ) -> None:
        self._graph = graph
        self._storage = storage
        self._llm = llm

    def synthesize(self, entity_name: str, query: str) -> InsightResponse:
        """
        Synthesize a narrative insight for stories mentioning entity_name.

        Args:
            entity_name: Entity to scope the query
            query: The user's question or pattern description

        Returns:
            InsightResponse with narrative and evidence

        Raises:
            LLMError: If the LLM call fails
            GraphError: If the graph query fails
        """
        total = self._graph.count_stories_by_entity(entity_name)
        if total == 0:
            return InsightResponse(narrative="", story_count=0)

        story_ids = self._graph.find_story_ids_by_entity(
            entity_name, limit=_MAX_STORIES, offset=0
        )
        stories = [self._storage.get_story(sid) for sid in story_ids]

        # Compute theme distribution
        theme_counts: dict[str, int] = {}
        for story in stories:
            for theme in story.themes:
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Compute sentiment summary
        pos_proc = neg_proc = neu_proc = 0
        pos_out = neg_out = neu_out = 0
        for story in stories:
            if story.sentiment is None:
                continue
            s = story.sentiment.process_sentiment.lower()
            if s == "positive":
                pos_proc += 1
            elif s == "negative":
                neg_proc += 1
            else:
                neu_proc += 1
            o = story.sentiment.outcome_sentiment.lower()
            if o == "positive":
                pos_out += 1
            elif o == "negative":
                neg_out += 1
            else:
                neu_out += 1

        sentiment_summary = SentimentSummary(
            positive_process=pos_proc,
            negative_process=neg_proc,
            neutral_process=neu_proc,
            positive_outcome=pos_out,
            negative_outcome=neg_out,
            neutral_outcome=neu_out,
        )

        # Build excerpts with triad positions
        excerpts = [
            StoryExcerpt(
                story_id=story.id,
                text_excerpt=story.story_text[:_EXCERPT_LEN],
                triad_positions={
                    p.triad_id: {"x": p.coordinates.x, "y": p.coordinates.y}
                    for p in story.triads
                },
            )
            for story in stories
        ]

        context = InsightContext(
            query=query,
            entity_name=entity_name,
            total_stories=total,
            excerpts=excerpts,
            theme_counts=theme_counts,
            sentiment_summary=sentiment_summary,
        )

        output: InsightOutput = self._llm.synthesize_insights(context)
        return InsightResponse(
            narrative=output.narrative,
            caveats=output.caveats,
            story_count=total,
            theme_counts=theme_counts,
            sentiment_summary=sentiment_summary,
            excerpts=excerpts,
        )
