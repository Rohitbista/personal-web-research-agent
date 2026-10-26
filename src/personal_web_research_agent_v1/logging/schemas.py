"""
logging/schemas.py

Pydantic models that define the shape of every structured log entry written
by AppLogger.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

from personal_web_research_agent_v1.config.settings import ENV, SERVICE_CODE


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _nepal_now() -> str:
    # Nepal is 5 hours and 45 minutes ahead of UTC
    nepal_tz = timezone(timedelta(hours=5, minutes=45))
    return datetime.now(nepal_tz).isoformat()


# ---------------------------------------------------------------------------
# AppLogger schema  (internal application events)
# ---------------------------------------------------------------------------

AppLogLevel = Literal["INFO", "DEBUG", "WARN", "ERROR"]


class AppLogEntry(BaseModel):
    """
    Structured log entry for internal application events.

    Fields map 1-to-1 to the parameters in LoggerService.info / .debug /
    .warn / .error.
    """

    environment: str = Field(default=ENV)
    timestamp: str = Field(default_factory=_nepal_now)
    service: str = Field(default=SERVICE_CODE)
    level: AppLogLevel
    message: str
    context: Optional[str] = None        # class / component where the log originated
    data: Optional[Any] = None           # arbitrary structured payload
    trace_id: Optional[str] = None       # correlation / request-tracing ID
    error: Optional[str] = None          # stringified error message (ERROR level only)
    error_stack: Optional[str] = None    # stack trace (ERROR level only)

    class Config:
        extra = "allow"                  # forward-compatible with future fields

# ---------------------------------------------------------------------------
# ApiLogger schema  (outbound LLM / third-party API calls)
# ---------------------------------------------------------------------------
 
class ApiLogEntry(BaseModel):
    """
    Structured log entry for every outbound API call (LLM, external services, etc.).
 
    Fields map 1-to-1 to ApiLogger.log_api_call parameters, with an additional
    `source` field to identify which external API was called.
    """
 
    environment: str = Field(default=ENV)
    timestamp: str = Field(default_factory=_nepal_now)
    service: str = Field(default=SERVICE_CODE)
    level: AppLogLevel
    source: Optional[str] = None         # which API: "llm", "usgs", "gdacs", …
    status: Optional[bool] = None        # IF True = success, False = failure
    request: Any                         # serialisable request details (url, params, messages, …)
    response: Optional[Any] = None       # serialisable response body / summary
    response_time_ms: Optional[str] = None
    trace_id: Optional[str] = None
    message: str
 
    class Config:
        extra = "allow"                  # forward-compatible with future fields