import asyncio
from fastapi import APIRouter, HTTPException
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
from personal_web_research_agent_v1.app.job_store import (
    create_job,
    get_job,
    get_session,
    get_jobs_for_session,
    list_sessions,
)
from personal_web_research_agent_v1.services.research_service import run_research_job

router = APIRouter(prefix="/api/v1", tags=["research"])


# ═══════════════════════════════════════════════════════════════════════════════
# Session endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sessions", response_model=SessionListResponse)
async def get_all_sessions():
    """
    List all sessions (newest first).
    Each session contains a lightweight history of its research jobs.
    """
    sessions = list_sessions()
    return SessionListResponse(
        sessions=[_build_session_response(s.id) for s in sessions]
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_detail(session_id: str):
    """Full detail for one session — title, timestamps, and its research history."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _build_session_response(session_id)


@router.patch("/sessions/{session_id}/rename", response_model=SessionResponse)
async def rename_session(session_id: str, request: RenameSessionRequest):
    """
    Rename a session's title.

    The title is set automatically from the first query when the session is
    created, but users can override it here at any time.
    ``{"title": "My custom title"}``
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title must not be empty")
    session.title = title
    return _build_session_response(session_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Research endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/research", response_model=StartResearchResponse, status_code=202)
async def start_research(request: StartResearchRequest):
    """
    Start a new research job.

    - ``session_id`` is optional. If omitted (or unknown), a new session is
      created automatically and its id is returned so the client can group
      follow-up queries under the same conversation.
    - Returns immediately; research runs in the background.
    """
    job = create_job(query=request.query, session_id=request.session_id)
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
    Each event is JSON: ``{"type": "searching" | "fetching" | "completed" | …, "data": "…"}``
    The stream closes automatically when the job finishes.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _event_generator():
        while True:
            payload = await job.events.get()
            if payload is None:      # sentinel → close the stream
                break
            yield {"data": payload}

    return EventSourceResponse(_event_generator())


@router.get("/research/{job_id}", response_model=ResearchStatusResponse)
async def get_research(job_id: str):
    """Poll job status. When ``status == 'completed'``, the ``report`` field is populated."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ResearchStatusResponse(
        research_id=job.id,
        session_id=job.session_id,
        status=job.status,
        query=job.query,
        report=job.report,
        error=job.error,
        created_at=job.created_at,
    )


@router.post("/research/{job_id}/cancel", status_code=200)
async def cancel_research(job_id: str):
    """Signal the background thread to stop after its current LangGraph chunk."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a job in '{job.status}' state",
        )
    job._cancel_event.set()
    job.status = "cancelled"
    return {"research_id": job_id, "status": "cancelled"}


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _build_session_response(session_id: str) -> SessionResponse:
    session = get_session(session_id)
    jobs = get_jobs_for_session(session_id)
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