"""
Dashboard API endpoints.

Provides aggregated theme/entity statistics and CSV/JSON export.
"""

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse

from src.api.stories import get_storage
from src.ports.storage import StoragePort
from src.services.dashboard import DashboardData, DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def get_dashboard_service(
    storage: StoragePort = Depends(get_storage),
) -> DashboardService:
    return DashboardService(storage=storage)


@router.get("")
async def get_dashboard(
    format: str | None = Query(default=None, description="Export format: json or csv"),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    service: DashboardService = Depends(get_dashboard_service),
) -> Response:
    """
    Return dashboard aggregation data.

    Optionally filtered by date range. Returns JSON by default;
    use ?format=csv for CSV export or ?format=json to force JSON
    with the correct Content-Type for browser download.
    """
    data = service.get_data(from_date=from_date, to_date=to_date)

    if format == "csv":
        return _csv_response(data)
    if format == "json":
        return _json_download_response(data)

    return JSONResponse(content=_to_dict(data))


def _to_dict(data: DashboardData) -> dict:
    return {
        "total_stories": data.total_stories,
        "top_themes": data.top_themes,
        "top_entities": data.top_entities,
        "recent_story_ids": data.recent_story_ids,
        "distinct_theme_count": data.distinct_theme_count,
        "distinct_entity_count": data.distinct_entity_count,
        "sample_capped": data.sample_capped,
    }


def _csv_response(data: DashboardData) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["section", "name", "count"])
    for t in data.top_themes:
        writer.writerow(["theme", t["name"], t["count"]])
    for e in data.top_entities:
        writer.writerow(["entity", e["name"], e["count"]])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dashboard.csv"},
    )


def _json_download_response(data: DashboardData) -> Response:
    content = json.dumps(_to_dict(data), indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=dashboard.json"},
    )
