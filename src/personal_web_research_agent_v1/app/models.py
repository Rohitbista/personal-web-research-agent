import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from personal_web_research_agent_v1.config.nepal_time import nepal_date_now


# ── Pydantic I/O models (HTTP layer) ─────────────────────────────────────────

class StartResearchRequest(BaseModel):
    query: str
    session_id: Optional[str] = None   # omit → a new session is created automatically


class StartResearchResponse(BaseModel):
    research_id: str
    session_id: str                    # always returned so the client can track it
    status: str


class ResearchStatusResponse(BaseModel):
    research_id: str
    session_id: str
    status: str          # queued | running | completed | failed | cancelled
    query: str
    report: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


class ResearchSummary(BaseModel):
    """Lightweight view of a job — used inside session listings."""
    research_id: str
    status: str
    query: str
    created_at: datetime


class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    research_history: List[ResearchSummary] = []


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]


class RenameSessionRequest(BaseModel):
    title: str


# ── Internal state (not sent over the wire directly) ─────────────────────────

@dataclass
class ResearchJob:
    id: str                        = field(default_factory=lambda: "research-"+str(uuid.uuid4()))
    query: str                     = ""
    session_id: str                = ""
    status: str                    = "queued"
    report: Optional[str]          = None
    error: Optional[str]           = None
    created_at: datetime           = field(default_factory=nepal_date_now)  # callable ✓

    # SSE event bus — one message per LangGraph node transition
    events: asyncio.Queue          = field(default_factory=asyncio.Queue)

    # Signals the background thread to stop gracefully
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    # Handle to the asyncio Task so we can inspect it
    task: Optional[asyncio.Task]   = None


@dataclass
class Session:
    id: str                        = field(default_factory=lambda: "session-"+str(uuid.uuid4()))
    title: str                     = ""          # set from first job's query
    created_at: datetime           = field(default_factory=nepal_date_now)  # callable ✓
    job_ids: List[str]             = field(default_factory=list)