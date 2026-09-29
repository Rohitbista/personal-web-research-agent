"""
logging/api_logger.py

ApiLogger — structured logger for every outbound API call (LLM calls,
third-party services, etc.).

One ApiLogger instance is created per external source.  Each instance writes
its JSON-structured ApiLogEntry records to its own dedicated log file inside
PERSIST_DIR_LOGS (from settings).  The file is named after the source:

    {PERSIST_DIR_LOGS}/llm.log
    {PERSIST_DIR_LOGS}/usgs.log
    {PERSIST_DIR_LOGS}/gdacs.log

The directory is created automatically on first use if it does not exist.
A human-readable summary line is also emitted to the console.

Usage
-----
    from basecamp_chatbot.logging.api_logger import get_api_logger

    llm_logger = get_api_logger(source="llm")
    llm_logger.log_api_call(
        status=True,
        request={"model": "...", "messages": [...]},
        response={"category": "Query", "usage": {...}},
        response_time_ms="142",
        trace_id="abc-123",
        message="classify_query LLM call",
    )
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from personal_web_research_agent_v1.config.settings import PERSIST_DIR_LOGS
from personal_web_research_agent_v1.logging.schemas import ApiLogEntry


# Registry of already-created instances (keyed by source name).
# Prevents duplicate handlers if the same source is requested twice.
_instances: dict[str, "ApiLogger"] = {}


class _ApiJsonFormatter(logging.Formatter):
    """Emit each API log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        entry: dict[str, Any] = record.__dict__.get("api_entry", {})
        if not entry:
            entry = {
                "timestamp": self.formatTime(record, self.datefmt),
                "message": record.getMessage(),
            }
        return json.dumps(entry, default=str, ensure_ascii=False)


class ApiLogger:
    """
    Per-source structured logger for outbound API calls.

    Parameters
    ----------
    source  : Short identifier for the external API, e.g. "llm", "usgs",
              "gdacs".  Included in every log entry and used as the log
              file name: ``{PERSIST_DIR_LOGS}/{source}.log``.
    level   : Python logging level (default: DEBUG).
    """

    def __init__(
        self,
        source: str,
        level: int = logging.DEBUG,
    ):
        self.source = source
        self._log_file = os.path.join(PERSIST_DIR_LOGS, f"{source}.log")
        self._log_dir = PERSIST_DIR_LOGS

        logger_name = f"api_logger.{source}"
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(level)
        self._logger.propagate = False

        if not self._logger.handlers:
            self._setup_handlers(level)

    # ── Private setup helpers ─────────────────────────────────────────────────

    def _setup_handlers(self, level: int) -> None:
        """Create the log directory and attach all handlers exactly once."""
        os.makedirs(self._log_dir, exist_ok=True)
        self._logger.addHandler(self._make_file_handler(level))
        self._logger.addHandler(self._make_console_handler(level))

    def _make_file_handler(self, level: int) -> logging.FileHandler:
        """JSON file handler — one log entry per line."""
        fh = logging.FileHandler(self._log_file, encoding="utf-8")
        fh.setFormatter(_ApiJsonFormatter())
        fh.setLevel(level)
        return fh

    def _make_console_handler(self, level: int) -> logging.StreamHandler:
        """Human-readable one-liner console handler."""
        ch = logging.StreamHandler()
        ch.setFormatter(
            logging.Formatter(
                f"%(asctime)s [API:{self.source.upper()}] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        ch.setLevel(level)
        return ch

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_api_call(
        self,
        *,
        status: Optional[bool] = None,
        request: Any,
        response: Optional[Any] = None,
        response_time_ms: Optional[str] = None,
        trace_id: Optional[str] = None,
        message: str,
    ) -> None:
        """
        Log a single outbound API interaction.

        Parameters
        ----------
        status           : True = success, False = failure, None = unknown.
                           Failures are logged at ERROR level so they stand
                           out in the file.
        request          : Serialisable request details (url, params, messages, …)
        response         : Serialisable response summary (status_code, body, …)
        response_time_ms : Elapsed time in milliseconds as a string
        trace_id         : Correlation / request-tracing ID
        message          : Human-readable description of the call
        """
        py_level = logging.ERROR if status is False else logging.INFO
        level_label: str = logging.getLevelName(py_level)  # "ERROR" or "INFO"

        entry = ApiLogEntry(
            level=level_label,  # type: ignore[arg-type]
            source=self.source,
            status=status,
            request=request,
            response=response,
            response_time_ms=response_time_ms,
            trace_id=trace_id,
            message=message,
        )

        record = self._logger.makeRecord(
            name=f"api_logger.{self.source}",
            level=py_level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.__dict__["api_entry"] = entry.dict(exclude_none=True)
        self._logger.handle(record)


# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------

def get_api_logger(
    source: str,
    level: int = logging.DEBUG,
) -> ApiLogger:
    """
    Return a cached ApiLogger for *source*, creating it on first call.

    The log file is created at ``{PERSIST_DIR_LOGS}/{source}.log``
    automatically if it does not exist.

    This ensures only one logger (and therefore one file handler) exists
    per source for the lifetime of the process.

    Parameters
    ----------
    source : Short identifier, e.g. "llm", "usgs", "gdacs".
    level  : Logging level (default: DEBUG).
    """
    if source not in _instances:
        _instances[source] = ApiLogger(source=source, level=level)
    return _instances[source]