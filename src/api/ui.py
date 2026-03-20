"""
UI routes serving Jinja2 HTML templates.

Handles story submission form rendering and form-based submission,
returning HTML fragments for HTMX to swap into the page.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from src.api.stories import get_submission_service
from src.ports.errors import StorageError
from src.services.story_submission import StorySubmissionRequest, StorySubmissionService

router = APIRouter(tags=["ui"])

_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "templates")
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
) -> HTMLResponse:
    """
    Accept story form submission and return an HTML fragment.

    Parses multipart/form-urlencoded data, builds a StorySubmissionRequest,
    and returns a confirmation or error HTML snippet for HTMX to swap.
    """
    form = await request.form()
    story_text = str(form.get("story_text", ""))
    triad_config = request.app.state.triad_config

    triads = []
    for triad in triad_config.triads:
        try:
            x = float(form.get(f"{triad.id}_x", 0.5))  # type: ignore[arg-type]
            y = float(form.get(f"{triad.id}_y", 0.5))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            x, y = 0.5, 0.5
        triads.append({"triad_id": triad.id, "x": x, "y": y})

    try:
        submission = StorySubmissionRequest(story_text=story_text, triads=triads)
        result = service.submit_story(submission)
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
