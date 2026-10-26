"""
logging/log_reader.py

Utility for reading, parsing, and filtering structured JSON log files.
Used by the log viewer API endpoint — not imported anywhere else.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Optional

from personal_web_research_agent_v1.config.settings import PERSIST_DIR_LOGS


# ---------------------------------------------------------------------------
# Log file registry
# ---------------------------------------------------------------------------

# Maps the ?source= query param value to the actual log file.
# "app" is special — it always points to app.log.
# Any other value is treated as an API source: {source}.log
def _resolve_log_file(source: str) -> str:
    if source == "app":
        return os.path.join(PERSIST_DIR_LOGS, "app.log")
    return os.path.join(PERSIST_DIR_LOGS, f"{source}.log")


def available_sources() -> list[str]:
    """
    Return a sorted list of log sources that have an existing log file.
    Used to populate the source dropdown in the template.
    """
    sources = ["app"]
    try:
        for name in os.listdir(PERSIST_DIR_LOGS):
            if name.endswith(".log") and name != "app.log":
                sources.append(name.removesuffix(".log"))
    except FileNotFoundError:
        pass
    return sorted(sources)


# ---------------------------------------------------------------------------
# Reader + filter
# ---------------------------------------------------------------------------

def read_logs(
    source: str = "app",
    level: Optional[str] = None,
    date_str: Optional[str] = None,
    trace_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
) -> tuple[list[dict], str | None]:
    """
    Read and filter a structured JSON log file.

    Parameters
    ----------
    source   : "app" for app.log, or any API source name ("llm", "usgs", …).
    level    : Filter to a single level — "INFO", "DEBUG", "WARN", "ERROR".
    date_str : ISO date string "YYYY-MM-DD" — keeps only entries from that day.
    trace_id : Exact trace_id match.
    search   : Case-insensitive substring match against the `message` field.
    limit    : Maximum number of entries to return (most recent first).

    Returns
    -------
    (entries, error) where error is None on success or an error string.
    """
    log_file = _resolve_log_file(source)

    if not os.path.exists(log_file):
        return [], f"Log file not found: {log_file}"

    entries: list[dict] = []
    parse_errors = 0

    with open(log_file, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            # ── Apply filters ────────────────────────────────────────────
            if level and entry.get("level", "").upper() != level.upper():
                continue

            if date_str:
                ts = entry.get("timestamp", "")
                if not ts.startswith(date_str):
                    continue

            if trace_id and entry.get("trace_id") != trace_id:
                continue

            if search:
                msg = entry.get("message", "").lower()
                if search.lower() not in msg:
                    continue

            entries.append(entry)

    # Most recent first, capped at limit
    entries = entries[-limit:][::-1]

    error = f"({parse_errors} malformed lines skipped)" if parse_errors else None
    return entries, error