"""
Insights API endpoints.

LLM-powered insight synthesis from pattern queries.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.api.stories import get_graph, get_llm, get_storage
from src.ports.errors import GraphError, LLMError, NotFoundError, QueryTranslationError, StorageError
from src.ports.graph import GraphPort
from src.ports.llm import LLMPort
from src.ports.storage import StoragePort
from src.services.insight_synthesis import InsightResponse, InsightSynthesisService
from src.services.nl_query import NLQueryResult, NLQueryService

router = APIRouter(prefix="/api/insights", tags=["insights"])


class SynthesizeRequest(BaseModel):
    entity_name: str = Field(min_length=1)
    query: str = Field(min_length=1)

    @field_validator("entity_name", "query")
    @classmethod
    def must_not_be_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank or whitespace only")
        return v


class SentimentSummaryResponse(BaseModel):
    positive_process: int
    negative_process: int
    neutral_process: int
    positive_outcome: int
    negative_outcome: int
    neutral_outcome: int


class StoryExcerptResponse(BaseModel):
    story_id: str
    text_excerpt: str
    triad_positions: dict[str, dict[str, float]]


class SynthesizeResponse(BaseModel):
    narrative: str
    story_count: int
    caveats: list[str]
    theme_counts: dict[str, int]
    sentiment_summary: SentimentSummaryResponse
    excerpts: list[StoryExcerptResponse]


def get_insight_synthesis_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> InsightSynthesisService:
    """Dependency that provides the insight synthesis service."""
    return InsightSynthesisService(graph=graph, storage=storage, llm=llm)


def get_nl_query_service(
    graph: GraphPort = Depends(get_graph),
    storage: StoragePort = Depends(get_storage),
    llm: LLMPort = Depends(get_llm),
) -> NLQueryService:
    """Dependency that provides the natural language query service."""
    return NLQueryService(graph=graph, storage=storage, llm=llm)


def _to_response(result: InsightResponse) -> SynthesizeResponse:
    return SynthesizeResponse(
        narrative=result.narrative,
        story_count=result.story_count,
        caveats=result.caveats,
        theme_counts=result.theme_counts,
        sentiment_summary=SentimentSummaryResponse(
            positive_process=result.sentiment_summary.positive_process,
            negative_process=result.sentiment_summary.negative_process,
            neutral_process=result.sentiment_summary.neutral_process,
            positive_outcome=result.sentiment_summary.positive_outcome,
            negative_outcome=result.sentiment_summary.negative_outcome,
            neutral_outcome=result.sentiment_summary.neutral_outcome,
        ),
        excerpts=[
            StoryExcerptResponse(
                story_id=e.story_id,
                text_excerpt=e.text_excerpt,
                triad_positions=e.triad_positions,
            )
            for e in result.excerpts
        ],
    )


class NLQueryRequest(BaseModel):
    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def must_not_be_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank or whitespace only")
        return v


class NLQueryResponse(BaseModel):
    answer: str
    story_count: int
    caveats: list[str]


@router.post("/query", response_model=NLQueryResponse)
async def query_insights(
    request: NLQueryRequest,
    service: NLQueryService = Depends(get_nl_query_service),
) -> NLQueryResponse:
    """
    Answer a natural language question about feedback patterns.

    The LLM translates the question into a graph query, retrieves matching
    stories, and synthesizes a plain-English answer.

    Args:
        request: question — a plain-English question about the feedback data

    Returns:
        NLQueryResponse with answer, story_count, and any caveats

    Raises:
        HTTPException 422: If the question cannot be translated to a graph query
        HTTPException 503: If the graph or LLM is unavailable
    """
    try:
        result = service.query(request.question)
    except QueryTranslationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except (GraphError, LLMError, StorageError, NotFoundError) as e:
        raise HTTPException(status_code=503, detail="Service unavailable") from e

    return NLQueryResponse(
        answer=result.answer,
        story_count=result.story_count,
        caveats=result.caveats,
    )


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_insights(
    request: SynthesizeRequest,
    service: InsightSynthesisService = Depends(get_insight_synthesis_service),
) -> SynthesizeResponse:
    """
    Synthesize a narrative explanation for patterns related to an entity.

    Retrieves stories mentioning entity_name from the graph, computes
    theme and sentiment statistics, and asks the LLM to generate a
    narrative explanation in response to the query.

    Note: MVP scope — entity-name query only. Free-text pattern retrieval
    requires additional graph capabilities.

    Args:
        request: entity_name and query string

    Returns:
        SynthesizeResponse with narrative, supporting evidence, and statistics

    Raises:
        HTTPException 503: If the graph or LLM is unavailable
    """
    try:
        result = service.synthesize(
            entity_name=request.entity_name, query=request.query
        )
    except GraphError as e:
        raise HTTPException(status_code=503, detail="Graph database unavailable") from e
    except LLMError as e:
        raise HTTPException(status_code=503, detail="LLM unavailable") from e
    except NotFoundError as e:
        raise HTTPException(status_code=503, detail="Story data inconsistency — retry later") from e
    except StorageError as e:
        raise HTTPException(status_code=503, detail="Storage unavailable") from e

    return _to_response(result)
