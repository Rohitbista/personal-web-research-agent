"""
logging/app_logger.py

AppLogger — structured logger for internal application events.

Writes two outputs simultaneously:
  1. A human-readable line to the console.
  2. A JSON-structured AppLogEntry to logs/app.log.

Design mirrors the AppLogger class referenced in logger.service.ts:
    appLogger.info(message, context?, data?, trace_id?)
    appLogger.debug(message, context?, data?, trace_id?)
    appLogger.warn(message, context?, data?, trace_id?)
    appLogger.error(message, context?, error?, data?, trace_id?)
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any, Optional

from .schemas import AppLogEntry


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        entry: dict[str, Any] = record.__dict__.get("structured_entry", {})
        if not entry:
            # Fallback for records not emitted by AppLogger
            entry = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "message": record.getMessage(),
                "context": record.name,
            }
        return json.dumps(entry, default=str, ensure_ascii=False)


class AppLogger:
    """
    Structured internal logger.

    Usage
    -----
    from logging.app_logger import AppLogger

    app_logger = AppLogger(log_file="logs/app.log")
    app_logger.info("Subscription fetched", context="MainOrchestrator",
                    data={"rows": 5}, trace_id="abc-123")
    """

    def __init__(self, log_file: str = "logs/app.log", level: int = logging.DEBUG):
        self._logger = logging.getLogger("app_logger")
        self._logger.setLevel(level)
        self._logger.propagate = False

        if not self._logger.handlers:
            # ── File handler (JSON) ───────────────────────────────────────
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(_JsonFormatter())
            fh.setLevel(level)
            self._logger.addHandler(fh)

            # ── Console handler (human-readable) ─────────────────────────
            ch = logging.StreamHandler()
            ch.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            ch.setLevel(level)
            self._logger.addHandler(ch)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def info(
        self,
        message: str,
        context: Optional[str] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self._emit(logging.INFO, "INFO", message, context, data, trace_id)

    def debug(
        self,
        message: str,
        context: Optional[str] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self._emit(logging.DEBUG, "DEBUG", message, context, data, trace_id)

    def warn(
        self,
        message: str,
        context: Optional[str] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self._emit(logging.WARNING, "WARN", message, context, data, trace_id)

    def error(
        self,
        message: str,
        context: Optional[str] = None,
        error: Optional[Exception] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        error_str: Optional[str] = None
        stack_str: Optional[str] = None

        if error is not None:
            error_str = str(error)
            stack_str = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )

        self._emit(
            logging.ERROR, "ERROR", message, context, data, trace_id,
            error=error_str, error_stack=stack_str,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _emit(
        self,
        py_level: int,
        level_label: str,
        message: str,
        context: Optional[str],
        data: Optional[Any],
        trace_id: Optional[str],
        error: Optional[str] = None,
        error_stack: Optional[str] = None,
    ) -> None:
        entry = AppLogEntry(
            level=level_label,       # type: ignore[arg-type]
            message=message,
            context=context,
            data=data,
            trace_id=trace_id,
            error=error,
            error_stack=error_stack,
        )
        record = self._logger.makeRecord(
            name=context or "app_logger",
            level=py_level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        record.__dict__["structured_entry"] = entry.dict(exclude_none=True)
        self._logger.handle(record)