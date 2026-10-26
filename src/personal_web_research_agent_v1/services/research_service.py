"""
services/research_service.py
─────────────────────────────
Runs the LangGraph graph in a background thread in two phases:
  1. run_research_job    → planner runs, graph pauses (interrupt_after planner)
  2. resume_research_job → optionally overwrite the plan, then continue
"""

import asyncio
import json
from typing import Any, Optional

from personal_web_research_agent_v1.agents.graph import app as langgraph_app
from personal_web_research_agent_v1.app.models import ResearchJob
from personal_web_research_agent_v1.database.database import SessionLocal
from personal_web_research_agent_v1.services import job_service


def graph_config(job_id: str) -> dict:
    # thread_id is REQUIRED by the checkpointer; job.id is unique per run
    return {"configurable": {"thread_id": job_id}, "recursion_limit": 25}


async def run_research_job(job: ResearchJob, trace_id: Optional[str] = None) -> None:
    """Phase 1: start the graph. It pauses after the planner."""
    inputs = {"messages": [("user", job.query)], "trace_id": trace_id}
    await _execute(job, inputs=inputs, trace_id=trace_id)


async def resume_research_job(
    job: ResearchJob,
    queries: Optional[list[str]],
    trace_id: Optional[str] = None,
) -> None:
    """Phase 2: apply the human's edits (if any) and continue."""
    await _execute(job, inputs=None, trace_id=trace_id, edited_queries=queries)


async def _execute(
    job: ResearchJob,
    *,
    inputs: Optional[dict],
    trace_id: Optional[str],
    edited_queries: Optional[list[str]] = None,
) -> None:
    loop = asyncio.get_running_loop()
    config = graph_config(job.id)
    paused = False   # set by the worker thread when the graph stops at the interrupt

    job.status = "running"
    _persist_status(job.id, status="running")

    def _emit(event_type: str, data: Any) -> None:
        payload = json.dumps({"type": event_type, "data": data})
        asyncio.run_coroutine_threadsafe(job.events.put(payload), loop)

    def _run() -> None:
        nonlocal paused
        try:
            # Human edits go into the checkpoint BEFORE resuming.
            if edited_queries is not None:
                langgraph_app.update_state(
                    config,
                    {"research_queries": edited_queries},
                    as_node="planner_node",   # so the next node is still researcher_node
                )
                _emit("plan_updated", edited_queries)

            # inputs=None → resume from the checkpoint
            for chunk in langgraph_app.stream(inputs, config=config, stream_mode="updates"):
                if job._cancel_event.is_set():
                    return

                for node_name, updates in chunk.items():

                    if node_name == "researcher_node":
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
                            _persist_status(job.id, status="completed", report=last.content)
                            _emit("completed", last.content)

            # Stream ended: finished, or paused at the interrupt?
            if job._cancel_event.is_set():
                return
            snapshot = langgraph_app.get_state(config)
            if snapshot.next:   # non-empty → there is still work to do → paused
                queries = snapshot.values.get("research_queries", [])
                job.status = "awaiting_approval"
                _persist_status(job.id, status="awaiting_approval")
                paused = True
                _emit("plan_ready", queries)

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            _persist_status(job.id, status="failed", error=str(exc))
            _emit("error", str(exc))

    try:
        await asyncio.to_thread(_run)
    except asyncio.CancelledError:
        job._cancel_event.set()
        job.status = "cancelled"
        _persist_status(job.id, status="cancelled")
        _emit("cancelled", "Research was cancelled.")
    finally:
        # Keep the SSE stream open while waiting for the human
        if not paused:
            asyncio.run_coroutine_threadsafe(job.events.put(None), loop)


async def cancel_waiting_job(job: ResearchJob) -> None:
    """Cancel a job paused at the approval gate (no worker thread is running)."""
    job._cancel_event.set()
    job.status = "cancelled"
    await job.events.put(json.dumps({"type": "cancelled", "data": "Research was cancelled."}))
    await job.events.put(None)   # close the SSE stream


def _persist_status(job_id: str, *, status: str, report: str | None = None, error: str | None = None) -> None:
    with SessionLocal() as db:
        job_service.update_job_status(db, job_id, status=status, report=report, error=error)