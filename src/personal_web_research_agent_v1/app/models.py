import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Pydantic I/O models (HTTP layer) ─────────────────────────────────────────

class StartResearchRequest(BaseModel):
    query: str
    session_id: str

class StartResearchResponse(BaseModel):
    research_id: str
    status: str

class ResearchStatusResponse(BaseModel):
    research_id: str
    status: str          # queued | running | completed | failed | cancelled
    query: str
    report: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


# ── Internal job state (not sent over the wire directly) ─────────────────────

@dataclass
class ResearchJob:
    id: str                      = field(default_factory=lambda: str(uuid.uuid4()))
    query: str                   = ""
    session_id: str              = ""
    status: str                  = "queued"
    report: Optional[str]        = None
    error: Optional[str]         = None
    created_at: datetime         = field(default_factory=datetime.utcnow)

    # SSE event bus — one message per LangGraph node transition
    events: asyncio.Queue        = field(default_factory=asyncio.Queue)

    # Signals the background thread to stop gracefully (threads can't be
    # killed outright; we check this flag between LangGraph chunks)
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    # Handle to the asyncio Task so we can inspect it
    task: Optional[asyncio.Task] = None

# Old chat

class ChatRequest(BaseModel):
    message: str
    session_id: str        # so you can track conversations

class ChatResponse(BaseModel):
    reply: str
    session_id: str