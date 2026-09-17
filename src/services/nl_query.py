"""
NLQueryService: translate natural language questions into graph queries and synthesize answers.
"""

from dataclasses import dataclass, field

from src.domain.models import InsightContext, SentimentSummary, StoryExcerpt
from src.ports.errors import QueryTranslationError
from src.ports.graph import GraphPort
from src.ports.llm import LLMPort
from src.ports.storage import StoragePort

_MAX_STORIES = 20
_EXCERPT_LEN = 300


@dataclass
class NLQueryResult:
    """
    Responsibilities:
    - Represent a synthesized answer with its supporting evidence

    Collaborators:
    - None
    """

    answer: str
    story_count: int
    caveats: list[str] = field(default_factory=list)


class NLQueryService:
    """
    Responsibilities:
    - Answer natural-language questions about feedback evidence
    - Ground answers in graph-selected stories and bounded synthesis context

    Collaborators:
    - LLMPort
    - GraphPort
    - StoragePort
    """

    def __init__(self, graph: GraphPort, storage: StoragePort, llm: LLMPort) -> None:
        self._graph = graph
        self._storage = storage
        self._llm = llm

    def query(self, question: str) -> NLQueryResult:
        """
        Translate a natural language question and return a synthesized answer.

        Args:
            question: The user's plain-English question

        Returns:
            NLQueryResult with answer and story_count.
            answer is empty string when no stories match the intent.

        Raises:
            QueryTranslationError: If the LLM cannot determine query intent
            LLMError: If any LLM call fails
            GraphError: If graph lookup fails
            NotFoundError: If a referenced story is missing from storage
        """
        intent = self._llm.translate_query(question)

        if intent.operation == "unknown":
            raise QueryTranslationError(
                intent.explanation or "Could not interpret your question as a graph query."
            )

        total, story_ids = self._dispatch_intent(intent)  # raises QueryTranslationError on bad intent

        if total == 0:
            return NLQueryResult(answer="", story_count=0)

        stories = [self._storage.get_story(sid) for sid in story_ids]

        # Theme distribution
        theme_counts: dict[str, int] = {}
        for story in stories:
            for theme in story.themes:
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

        # Sentiment summary
        pos_proc = neg_proc = neu_proc = pos_out = neg_out = neu_out = 0
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

        excerpts = [
            StoryExcerpt(
                story_id=story.id,
                text_excerpt=story.story_text[:_EXCERPT_LEN],
                triad_positions={
                    r.signifier_id: {"x": r.coordinates.x, "y": r.coordinates.y}
                    for r in (story.signification.responses if story.signification else [])
                },
            )
            for story in stories
        ]

        # Label the synthesis scope clearly so the LLM prompt frames it correctly
        scope_label = (
            intent.entity if intent.operation == "by_entity"
            else f"theme '{intent.theme}'" if intent.operation == "by_theme"
            else ""
        )
        context = InsightContext(
            query=question,
            entity_name=scope_label,
            total_stories=total,
            excerpts=excerpts,
            theme_counts=theme_counts,
            sentiment_summary=sentiment_summary,
        )

        output = self._llm.synthesize_insights(context)
        return NLQueryResult(
            answer=output.narrative,
            story_count=total,
            caveats=output.caveats,
        )

    def _dispatch_intent(self, intent) -> tuple[int, list[str]]:
        """
        Return (total_count, story_ids) based on intent operation.

        Raises:
            QueryTranslationError: If the operation is unrecognized or required
                                   field (entity/theme) is missing.
        """
        if intent.operation == "by_entity":
            if not intent.entity:
                raise QueryTranslationError(
                    "Query translated as entity lookup but no entity name was provided."
                )
            total = self._graph.count_stories_by_entity(intent.entity)
            story_ids = self._graph.find_story_ids_by_entity(
                intent.entity, limit=_MAX_STORIES, offset=0
            )
            return total, story_ids

        if intent.operation == "by_theme":
            if not intent.theme:
                raise QueryTranslationError(
                    "Query translated as theme lookup but no theme name was provided."
                )
            total = self._graph.count_stories_by_theme(intent.theme)
            story_ids = self._graph.find_story_ids_by_theme(
                intent.theme, limit=_MAX_STORIES, offset=0
            )
            return total, story_ids

        raise QueryTranslationError(
            f"Unrecognized query operation '{intent.operation}'. "
            "Expected 'by_entity' or 'by_theme'."
        )
