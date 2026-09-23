import asyncio
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from personal_web_research_agent_v1.app.models import (
    StartResearchRequest, StartResearchResponse, ResearchStatusResponse
)
from personal_web_research_agent_v1.app.job_store import create_job, get_job
from personal_web_research_agent_v1.services.research_service import run_research_job

router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.post("", response_model=StartResearchResponse, status_code=202)
async def start_research(request: StartResearchRequest):
    """Creates a job and returns immediately — research runs in the background."""
    job = create_job(query=request.query, session_id=request.session_id)
    job.task = asyncio.create_task(run_research_job(job))
    return StartResearchResponse(research_id=job.id, status=job.status)


@router.get("/{job_id}/stream")
async def stream_research(job_id: str):
    """
    SSE stream of real-time progress events.
    Each event is JSON: {"type": "searching" | "fetching" | "completed" | ..., "data": "..."}
    Stream closes automatically when the job finishes.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _event_generator():
        while True:
            payload = await job.events.get()
            if payload is None:          # sentinel → close the stream
                break
            yield {"data": payload}

    return EventSourceResponse(_event_generator())


@router.get("/{job_id}", response_model=ResearchStatusResponse)
async def get_research(job_id: str):
    """Polls job status. When status == 'completed', the report field is populated."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ResearchStatusResponse(
        research_id=job.id,
        status=job.status,
        query=job.query,
        report=job.report,
        error=job.error,
        created_at=job.created_at,
    )


@router.post("/{job_id}/cancel", status_code=200)
async def cancel_research(job_id: str):
    """Signals the background thread to stop after its current chunk."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a job in '{job.status}' state"
        )
    job._cancel_event.set()
    job.status = "cancelled"
    return {"research_id": job_id, "status": "cancelled"}