"""
services/job_service.py
────────────────────────
Manages the two parallel representations of a research job:

  1. ResearchJobRecord  — the SQLite row (persistent fields only)
  2. ResearchJob        — the in-memory dataclass (asyncio.Queue, threading.Event,
                          asyncio.Task) that can never be serialised

The in-memory registry (_live_jobs) is intentionally process-local.
If you move to multi-worker deployments, replace it with a distributed
queue (e.g. Redis Streams) and keep only the DB for state.
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from personal_web_research_agent_v1.app.models import ResearchJob
from personal_web_research_agent_v1.database.models import ResearchJobRecord, SessionRecord

# ── In-memory registry for live SSE handles ───────────────────────────────────
# Keyed by job id.  Populated when a job is created, never persisted.
_live_jobs: dict[str, ResearchJob] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def create_job(
    db: DBSession,
    *,
    query: str,
    session_id: str,
) -> ResearchJob:
    """
    Persist a new job row and register a live handle.

    The caller is responsible for ensuring the session already exists in the DB.
    """
    job_id = f"research-job-{str(uuid.uuid4())}"

    # 1. Persist to SQLite
    record = ResearchJobRecord(
        id=job_id,
        session_id=session_id,
        query=query,
        status="queued",
    )
    db.add(record)
    db.commit()

    # 2. Build the in-memory live handle (Queue, Event, Task are not DB-safe)
    live = ResearchJob(id=job_id, query=query, session_id=session_id)
    _live_jobs[job_id] = live

    return live


def get_live_job(job_id: str) -> Optional[ResearchJob]:
    """
    Return the in-memory handle for SSE streaming / cancellation.
    Returns None if the server was restarted and the handle is gone.
    """
    return _live_jobs.get(job_id)


def get_job_record(db: DBSession, job_id: str) -> Optional[ResearchJobRecord]:
    """Return the persisted DB row for a job (used for status polling)."""
    return db.get(ResearchJobRecord, job_id)


def update_job_status(
    db: DBSession,
    job_id: str,
    *,
    status: str,
    report: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    Write status / report / error back to SQLite.
    Called by research_service as the LangGraph job progresses.
    """
    record = db.get(ResearchJobRecord, job_id)
    if not record:
        return
    record.status = status
    if report is not None:
        record.report = report
    if error is not None:
        record.error = error
    db.commit()


def get_jobs_for_session(
    db: DBSession, session_id: str
) -> list[ResearchJobRecord]:
    """Return all job rows for a session, in creation order."""
    return (
        db.query(ResearchJobRecord)
        .filter(ResearchJobRecord.session_id == session_id)
        .order_by(ResearchJobRecord.created_at)
        .all()
    )