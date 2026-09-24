"""
app/routes/research.py
───────────────────────
FastAPI router.  All business logic and persistence go through the
services layer; this file only handles HTTP concerns.
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from personal_web_research_agent_v1.app.models import (
    StartResearchRequest,
    StartResearchResponse,
    ResearchStatusResponse,
    ResearchSummary,
    SessionResponse,
    SessionListResponse,
    RenameSessionRequest,
)
from personal_web_research_agent_v1.database.database import get_db
from personal_web_research_agent_v1.services import session_service, job_service
from personal_web_research_agent_v1.services.research_service import run_research_job

router = APIRouter(prefix="/api/v1", tags=["research"])


# ═══════════════════════════════════════════════════════════════════════════════
# Session endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sessions", response_model=SessionListResponse)
def get_all_sessions(db: Session = Depends(get_db)):
    """List all sessions (newest first) with lightweight research history."""
    records = session_service.list_sessions(db)
    return SessionListResponse(
        sessions=[_build_session_response(db, r.id) for r in records]
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    """Full detail for one session — title, timestamps, and research history."""
    if not session_service.get_session(db, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return _build_session_response(db, session_id)


@router.patch("/sessions/{session_id}/rename", response_model=SessionResponse)
def rename_session(
    session_id: str,
    request: RenameSessionRequest,
    db: Session = Depends(get_db),
):
    """
    Rename a session's title.
    The title is auto-set from the first query on creation; this overrides it.
    """
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title must not be empty")
    record = session_service.rename_session(db, session_id, title)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return _build_session_response(db, session_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Research endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/research", response_model=StartResearchResponse, status_code=202)
async def start_research(
    request: StartResearchRequest,
    db: Session = Depends(get_db),
):
    """
    Start a new research job.

    ``session_id`` is optional — a new session is created automatically when
    omitted (or when the supplied id is not found in the DB).
    Returns immediately; research runs in the background.
    """
    # Resolve or auto-create the session
    session_id = request.session_id
    if session_id:
        existing = session_service.get_session(db, session_id)
        if not existing:
            # Client sent an id we don't know — treat as new session
            title = _auto_title(request.query)
            session_service.create_session(db, title=title, session_id=session_id)
    else:
        title = _auto_title(request.query)
        sess = session_service.create_session(db, title=title)
        session_id = sess.id

    job = job_service.create_job(db, query=request.query, session_id=session_id)
    job.task = asyncio.create_task(run_research_job(job))

    return StartResearchResponse(
        research_id=job.id,
        session_id=job.session_id,
        status=job.status,
    )


@router.get("/research/{job_id}/stream")
async def stream_research(job_id: str):
    """
    SSE stream of real-time progress events for a single research job.
    Each event is JSON: ``{"type": "searching"|"fetching"|"completed"|…, "data": "…"}``
    The stream closes automatically when the job finishes.

    Note: uses the in-memory live handle (not the DB) because the Queue
    and asyncio primitives cannot be stored in SQLite.
    """
    job = job_service.get_live_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or server was restarted (SSE unavailable for past jobs)",
        )

    async def _event_generator():
        while True:
            payload = await job.events.get()
            if payload is None:      # sentinel → close the stream
                break
            yield {"data": payload}

    return EventSourceResponse(_event_generator())


@router.get("/research/{job_id}", response_model=ResearchStatusResponse)
def get_research(job_id: str, db: Session = Depends(get_db)):
    """
    Poll job status.  When ``status == 'completed'`` the ``report`` field is populated.
    This reads from the DB so it works even after a server restart.
    """
    record = job_service.get_job_record(db, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return ResearchStatusResponse(
        research_id=record.id,
        session_id=record.session_id,
        status=record.status,
        query=record.query,
        report=record.report,
        error=record.error,
        created_at=record.created_at,
    )


@router.post("/research/{job_id}/cancel", status_code=200)
def cancel_research(job_id: str, db: Session = Depends(get_db)):
    """Signal the background thread to stop after its current LangGraph chunk."""
    record = job_service.get_job_record(db, job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status not in ("queued", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a job in '{record.status}' state",
        )
    # Signal the live handle (if the server hasn't restarted)
    live = job_service.get_live_job(job_id)
    if live:
        live._cancel_event.set()

    job_service.update_job_status(db, job_id, status="cancelled")
    return {"research_id": job_id, "status": "cancelled"}


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _auto_title(query: str) -> str:
    """Derive a session title from the first query (60 chars max)."""
    return query[:60].rstrip() + ("…" if len(query) > 60 else "")


def _build_session_response(db: Session, session_id: str) -> SessionResponse:
    session = session_service.get_session(db, session_id)
    jobs = job_service.get_jobs_for_session(db, session_id)
    return SessionResponse(
        session_id=session.id,
        title=session.title,
        created_at=session.created_at,
        research_history=[
            ResearchSummary(
                research_id=j.id,
                status=j.status,
                query=j.query,
                created_at=j.created_at,
            )
            for j in jobs
        ],
    )