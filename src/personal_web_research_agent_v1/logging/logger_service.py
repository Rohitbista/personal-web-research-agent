"""
logging/logger_service.py

LoggerService — the single import your application code uses.

Owns one AppLogger that writes structured JSON entries to the directory
defined by PERSIST_DIR_LOGS in settings.py.

Bootstrap (call ONCE at process start, before any other import that logs):

    from app_logging.logger_service import LoggerService
    LoggerService()

Then in every module:

    from app_logging.logger_service import LoggerService
    logger = LoggerService.get_instance()

    logger.info("Something happened", context="MyModule",
                data={"key": "val"}, trace_id="abc")
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Optional

from personal_web_research_agent_v1.config.settings import PERSIST_DIR_LOGS
from personal_web_research_agent_v1.logging.api_logger import ApiLogger, get_api_logger
from .app_logger import AppLogger

_APP_LOG = os.path.join(PERSIST_DIR_LOGS, "app.log")

# Singleton instance
_instance: Optional["LoggerService"] = None


class LoggerService:
    """
    Unified logging facade — app events only.

    Mirrors logger.service.ts method names and parameter order.
    """

    # ------------------------------------------------------------------
    # Construction / singleton
    # ------------------------------------------------------------------

    def __init__(
        self,
        log_dir: str = PERSIST_DIR_LOGS,
        level: int = logging.INFO,
    ):
        global _instance

        os.makedirs(log_dir, exist_ok=True)

        app_log = os.path.join(log_dir, "app.log")

        # ── Internal app logger ───────────────────────────────────────────
        self.app_logger = AppLogger(log_file=app_log, level=level)

        # ── Per-source API loggers (created lazily on first use) ──────────
        self._api_loggers: dict[str, ApiLogger] = {}

        # ── Replace stdlib root logger ────────────────────────────────────
        self._configure_root_logger(level, app_log)

        _instance = self
        self.app_logger.info(
            "LoggerService initialised",
            context="LoggerService",
            data={"app_log": app_log},
        )

    @staticmethod
    def get_instance() -> "LoggerService":
        """Return the singleton. Raises if LoggerService() was never called."""
        if _instance is None:
            raise RuntimeError(
                "LoggerService has not been initialised. "
                "Call LoggerService() once at process start."
            )
        return _instance

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def info(
        self,
        message: str,
        context: Optional[str] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.app_logger.info(message, context, data, trace_id)

    def debug(
        self,
        message: str,
        context: Optional[str] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.app_logger.debug(message, context, data, trace_id)

    def warn(
        self,
        message: str,
        context: Optional[str] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.app_logger.warn(message, context, data, trace_id)

    def error(
        self,
        message: str,
        context: Optional[str] = None,
        error: Optional[Exception] = None,
        data: Optional[Any] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.app_logger.error(message, context, error, data, trace_id)

    # ------------------------------------------------------------------
    # ApiLogger method  (third-party API calls)
    # ------------------------------------------------------------------

    def log_api_call(
        self,
        *,
        source: str,
        status: Optional[bool] = None,
        request: Any,
        response: Optional[Any] = None,
        response_time_ms: Optional[str] = None,
        trace_id: Optional[str] = None,
        message: str,
    ) -> None:
        """
        Log a third-party API call to its dedicated log file.

        Parameters
        ----------
        source           : Which external API — "usgs", "gdacs",
                           "openweather_current", "openweather_aqi", …
                           Determines which log file the entry is written to.
        status           : True = success, False = failure
        request          : Serialisable request details (url, params, …)
        response         : Serialisable response summary
        response_time_ms : Elapsed milliseconds as string
        trace_id         : Correlation ID
        message          : Human-readable description
        """
        api_logger = self._get_or_create_api_logger(source)
        api_logger.log_api_call(
            status=status,
            request=request,
            response=response,
            response_time_ms=response_time_ms,
            trace_id=trace_id,
            message=message,
        )

     # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_api_logger(self, source: str) -> ApiLogger:
        """Return existing ApiLogger for source, or create one on first use."""
        if source not in self._api_loggers:
            self._api_loggers[source] = get_api_logger(source)
            self.app_logger.info(
                f"Created new ApiLogger for unregistered source '{source}'",
                context="LoggerService",
            )
        return self._api_loggers[source]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _configure_root_logger(level: int, app_log: str) -> None:
        """
        Fully replace Python's root logger configuration.

        - Removes any pre-existing handlers.
        - Adds a console handler and a plain-text file handler.
        - Silences noisy third-party loggers.
        """
        root = logging.getLogger()

        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()

        root.setLevel(level)

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(fmt)
        root.addHandler(ch)

        # Plain-text file handler (for stdlib getLogger callers)
        fh = logging.FileHandler(app_log, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)

        # Silence noisy third-party libraries
        for noisy in ("httpx", "httpcore", "boto3", "botocore", "urllib3", "schedule"):
            logging.getLogger(noisy).setLevel(logging.WARNING)