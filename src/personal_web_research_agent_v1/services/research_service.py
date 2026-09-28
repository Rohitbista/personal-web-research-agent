"""
services/research_service.py
─────────────────────────────
Runs the LangGraph graph in a background thread, emits SSE events,
and persists every status transition back to SQLite via job_service.
"""

import asyncio
import json

from personal_web_research_agent_v1.agents.graph import app as langgraph_app
from personal_web_research_agent_v1.app.models import ResearchJob
from personal_web_research_agent_v1.database.database import SessionLocal
from personal_web_research_agent_v1.services import job_service


async def run_research_job(job: ResearchJob) -> None:
    """
    Runs the LangGraph graph inside a thread (it's synchronous) and
    emits SSE events back to the async event loop via the job's Queue.
    Status changes are written to SQLite at each transition.
    """
    loop = asyncio.get_running_loop()

    # ── persist: running ──────────────────────────────────────────────────────
    job.status = "running"
    _persist_status(job.id, status="running")

    def _emit(event_type: str, data: str) -> None:
        """Thread-safe: pushes a JSON event onto the job's async Queue."""
        payload = json.dumps({"type": event_type, "data": data})
        asyncio.run_coroutine_threadsafe(job.events.put(payload), loop)

    def _run() -> None:
        inputs = {"messages": [("user", job.query)]}
        config = {"recursion_limit": 25}

        try:
            for chunk in langgraph_app.stream(inputs, config=config, stream_mode="updates"):

                if job._cancel_event.is_set():
                    break

                for node_name, updates in chunk.items():

                    if node_name == "planner_node":
                        queries = updates.get("research_queries", [])
                        _emit(
                            "planning",
                            f"Plan ready — {len(queries)} queries: "
                            f"{', '.join(queries)}",
                        )

                    elif node_name == "researcher_node":
                        msgs = updates.get("messages", [])
                        last = msgs[-1] if msgs else None
                        if last and getattr(last, "tool_calls", None):
                            for tc in last.tool_calls:
                                name = tc["name"]
                                args = tc.get("args", {})
                                if name == "web_search":
                                    _emit("searching", f"Searching: \"{args.get('query', '')}\"")
                                elif name == "fetch_url_content":
                                    _emit("fetching", f"Fetching: {args.get('url', '')}")

                    elif node_name == "tools_node":
                        _emit("tool_done", "Results received, continuing…")

                    elif node_name == "synthesizer_node":
                        msgs = updates.get("messages", [])
                        last = msgs[-1] if msgs else None
                        if last and last.content:
                            job.report = last.content
                            job.status = "completed"
                            # ── persist: completed ────────────────────────────
                            _persist_status(job.id, status="completed", report=last.content)
                            _emit("completed", last.content)

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            # ── persist: failed ───────────────────────────────────────────────
            _persist_status(job.id, status="failed", error=str(exc))
            _emit("error", str(exc))

    try:
        await asyncio.to_thread(_run)
    except asyncio.CancelledError:
        job._cancel_event.set()
        job.status = "cancelled"
        # ── persist: cancelled ────────────────────────────────────────────────
        _persist_status(job.id, status="cancelled")
        _emit("cancelled", "Research was cancelled.")
    finally:
        asyncio.run_coroutine_threadsafe(job.events.put(None), loop)


# ── Internal helper ───────────────────────────────────────────────────────────

def _persist_status(
    job_id: str,
    *,
    status: str,
    report: str | None = None,
    error: str | None = None,
) -> None:
    """
    Opens a *new* DB session for each write.

    We can't reuse the request-scoped session here because this runs
    inside asyncio.to_thread (a worker thread), not in the FastAPI request
    context where get_db() is active.
    """
    with SessionLocal() as db:
        job_service.update_job_status(
            db, job_id, status=status, report=report, error=error
        )