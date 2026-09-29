"""
app/routes/log_viewer_router.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from personal_web_research_agent_v1.logging.log_reader import available_sources, read_logs
from fastapi.templating import Jinja2Templates

router = APIRouter()

_DIR = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR = _DIR / "logging" / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def log_viewer(
    request: Request,
    source: str = "app",
    level: Optional[str] = None,
    date: Optional[str] = str(date.today()),
    trace_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
):
    limit = min(limit, 500)

    entries, error = read_logs(
        source=source,
        level=level or None,
        date_str=date or None,
        trace_id=trace_id or None,
        search=search or None,
        limit=limit,
    )

    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={
            "entries": entries,
            "total": len(entries),
            "error": error,
            "sources": available_sources(),
            "levels": ["INFO", "DEBUG", "WARN", "ERROR"],
            "filters": {
                "source": source,
                "level": level or "",
                "date": date or "",
                "trace_id": trace_id or "",
                "search": search or "",
                "limit": limit,
            },
        },
    )