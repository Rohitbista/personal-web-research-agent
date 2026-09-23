from typing import Dict, Optional
from .models import ResearchJob

# In-memory. Replace with Redis + pickle/JSON for multi-process / persistence.
_store: Dict[str, ResearchJob] = {}


def create_job(query: str, session_id: str) -> ResearchJob:
    job = ResearchJob(query=query, session_id=session_id)
    _store[job.id] = job
    return job


def get_job(job_id: str) -> Optional[ResearchJob]:
    return _store.get(job_id)