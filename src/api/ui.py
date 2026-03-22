"""
UI routes serving Jinja2 HTML templates.

Handles story submission form rendering and form-based submission,
returning HTML fragments for HTMX to swap into the page.
"""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from src.api.insights import get_insight_synthesis_service, get_nl_query_service
from src.api.stories import (
    get_queue,
    get_storage,
    get_submission_service,
)
from src.ports.errors import GraphError, LLMError, NotFoundError, QueryTranslationError, StorageError
from src.ports.storage import StoragePort
from src.services.dashboard import DashboardService
from src.workers.worker_queue import WorkerQueue
from src.services.insight_synthesis import InsightSynthesisService
from src.services.nl_query import NLQueryService
from src.services.story_submission import StorySubmissionRequest, StorySubmissionService

router = APIRouter(tags=["ui"])

_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "templates")
)


def _get_dashboard_service(
    storage: StoragePort = Depends(get_storage),
) -> DashboardService:
    return DashboardService(storage=storage)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Pattern exploration dashboard."""
    return _templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={},
    )


@router.get("/dashboard/data", response_class=HTMLResponse)
async def dashboard_data(
    request: Request,
    service: DashboardService = Depends(_get_dashboard_service),
) -> HTMLResponse:
    """HTML fragment: aggregated stats for HTMX to swap into the dashboard."""
    from_date_str = request.query_params.get("from_date")
    to_date_str = request.query_params.get("to_date")

    try:
        from_date = datetime.fromisoformat(from_date_str) if from_date_str else None
        to_date = datetime.fromisoformat(to_date_str) if to_date_str else None
    except ValueError:
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": "Invalid date format. Use YYYY-MM-DD."},
            status_code=400,
        )

    data = service.get_data(from_date=from_date, to_date=to_date)
    return _templates.TemplateResponse(
        request=request,
        name="_dashboard_data.html",
        context={"data": data},
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Story submission form."""
    triads = request.app.state.triad_config.triads
    return _templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"triads": triads},
    )


@router.post("/ui/submit", response_class=HTMLResponse)
async def submit_story_form(
    request: Request,
    service: StorySubmissionService = Depends(get_submission_service),
    queue: WorkerQueue = Depends(get_queue),
) -> HTMLResponse:
    """
    Accept story form submission and return an HTML fragment.

    Parses multipart/form-urlencoded data, builds a StorySubmissionRequest,
    and returns a confirmation or error HTML snippet for HTMX to swap.
    """
    form = await request.form()
    story_text = str(form.get("story_text", ""))
    triad_config = request.app.state.triad_config

    responses = []
    for triad in triad_config.triads:
        try:
            x = float(form.get(f"{triad.id}_x", 0.5))  # type: ignore[arg-type]
            y = float(form.get(f"{triad.id}_y", 0.5))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            x, y = 0.5, 0.5
        responses.append({
            "kind": "triad",
            "signifier_id": triad.id,
            "coordinates": {"x": x, "y": y},
        })

    try:
        submission = StorySubmissionRequest(
            story_text=story_text,
            signification={"responses": responses},
        )
        result = service.submit_story(submission)
        queue.enqueue(result.story_id)
        return _templates.TemplateResponse(
            request=request,
            name="_confirmation.html",
            context={"story_id": result.story_id},
        )
    except ValidationError as e:
        first_error = e.errors()[0].get("msg", "Invalid submission")
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": first_error},
            status_code=400,
        )
    except StorageError:
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": "Submission failed — please try again."},
            status_code=503,
        )


@router.get("/query", response_class=HTMLResponse)
async def query_page(request: Request) -> HTMLResponse:
    """Natural language query chat page."""
    return _templates.TemplateResponse(
        request=request,
        name="query.html",
        context={},
    )


@router.post("/ui/query", response_class=HTMLResponse)
async def query_fragment(
    request: Request,
    service: NLQueryService = Depends(get_nl_query_service),
) -> HTMLResponse:
    """Accept a natural language question and return an HTML fragment with the answer."""
    form = await request.form()
    question = str(form.get("question", "")).strip()

    if not question:
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": "Question must not be blank."},
            status_code=400,
        )

    try:
        result = service.query(question)
        return _templates.TemplateResponse(
            request=request,
            name="_query_response.html",
            context={
                "question": question,
                "answer": result.answer,
                "caveats": result.caveats,
                "story_count": result.story_count,
            },
        )
    except QueryTranslationError as e:
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": str(e)},
            status_code=400,
        )
    except (GraphError, LLMError, NotFoundError, StorageError):
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": "Query service unavailable — please try again later."},
            status_code=503,
        )


@router.post("/ui/insights", response_class=HTMLResponse)
async def synthesize_insight_fragment(
    request: Request,
    service: InsightSynthesisService = Depends(get_insight_synthesis_service),
) -> HTMLResponse:
    """Return a narrative insight as an HTML fragment for the dashboard panel."""
    form = await request.form()
    entity_name = str(form.get("entity_name", "")).strip()
    query = str(form.get("query", "")).strip()

    if not entity_name or not query:
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": "entity_name and query are required."},
            status_code=400,
        )

    try:
        result = service.synthesize(entity_name=entity_name, query=query)
        return _templates.TemplateResponse(
            request=request,
            name="_insight.html",
            context={"result": result, "entity_name": entity_name},
        )
    except (GraphError, LLMError, NotFoundError, StorageError):
        return _templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={"error": "Insight synthesis unavailable — please try again later."},
            status_code=503,
        )
