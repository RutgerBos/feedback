"""
UI routes serving Jinja2 HTML templates.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.config.triad_loader import load_triad_config

router = APIRouter(tags=["ui"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))
_triad_config = load_triad_config(Path("config/triads.yaml"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Story submission form."""
    return _templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"triads": _triad_config.triads},
    )
