from typing import Dict, List, Optional
from .models import ResearchJob, Session

# In-memory stores.
# Replace with Redis + pickle/JSON for multi-process / persistence.
_jobs: Dict[str, ResearchJob] = {}
_sessions: Dict[str, Session] = {}


# ── Session helpers ───────────────────────────────────────────────────────────

def create_session(title: str = "") -> Session:
    """Create and persist a new session."""
    session = Session(title=title)
    _sessions[session.id] = session
    return session


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)


def list_sessions() -> List[Session]:
    """Return all sessions, newest first."""
    return sorted(_sessions.values(), key=lambda s: s.created_at, reverse=True)


# ── Job helpers ───────────────────────────────────────────────────────────────

def create_job(query: str, session_id: Optional[str] = None) -> ResearchJob:
    """
    Create a job and attach it to a session.

    - If ``session_id`` is provided and exists, the job is appended to that session.
    - If ``session_id`` is provided but unknown, a new session is created with that id
      (useful if the client is replaying a known id after a server restart).
    - If ``session_id`` is None, a fresh session is created automatically.
    """
    # Resolve / create the session
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
    else:
        # Auto-title: first ~60 chars of the query
        title = query[:60].rstrip() + ("…" if len(query) > 60 else "")
        # Pass an explicit id when the client supplied one so we honour it
        # without a post-construction mutation.
        session = Session(id=session_id, title=title) if session_id else Session(title=title)
        _sessions[session.id] = session

    job = ResearchJob(query=query, session_id=session.id)
    _jobs[job.id] = job
    session.job_ids.append(job.id)

    return job


def get_job(job_id: str) -> Optional[ResearchJob]:
    return _jobs.get(job_id)


def get_jobs_for_session(session_id: str) -> List[ResearchJob]:
    """Return all jobs belonging to a session, in creation order."""
    session = _sessions.get(session_id)
    if not session:
        return []
    return [_jobs[jid] for jid in session.job_ids if jid in _jobs]