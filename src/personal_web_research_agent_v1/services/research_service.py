import asyncio
import json
from personal_web_research_agent_v1.agents.graph import app as langgraph_app
from personal_web_research_agent_v1.app.models import ResearchJob


async def run_research_job(job: ResearchJob) -> None:
    """
    Runs the LangGraph graph inside a thread (it's synchronous) and
    emits SSE events back to the async event loop via the job's Queue.
    """
    loop = asyncio.get_running_loop()
    job.status = "running"

    def _emit(event_type: str, data: str) -> None:
        """Thread-safe: pushes an event onto the job's async Queue."""
        payload = json.dumps({"type": event_type, "data": data})
        asyncio.run_coroutine_threadsafe(job.events.put(payload), loop)

    def _run() -> None:
        inputs = {"messages": [("user", job.query)]}
        config = {"recursion_limit": 25}

        try:
            # stream_mode="updates" gives {node_name: state_delta} per step
            for chunk in langgraph_app.stream(inputs, config=config, stream_mode="updates"):

                # Honour a cancellation request between chunks
                if job._cancel_event.is_set():
                    break

                for node_name, updates in chunk.items():

                    if node_name == "planner_node":
                        queries = updates.get("research_queries", [])
                        _emit("planning",
                              f"Plan ready — {len(queries)} queries: "
                              f"{', '.join(queries)}")

                    elif node_name == "researcher_node":
                        msgs = updates.get("messages", [])
                        last = msgs[-1] if msgs else None
                        if last and getattr(last, "tool_calls", None):
                            for tc in last.tool_calls:
                                name = tc["name"]
                                args = tc.get("args", {})
                                if name == "web_search":
                                    _emit("searching",
                                          f"Searching: \"{args.get('query', '')}\"")
                                elif name == "fetch_url_content":
                                    _emit("fetching",
                                          f"Fetching: {args.get('url', '')}")

                    elif node_name == "tools_node":
                        _emit("tool_done", "Results received, continuing…")

                    elif node_name == "synthesizer_node":
                        msgs = updates.get("messages", [])
                        last = msgs[-1] if msgs else None
                        if last and last.content:
                            job.report = last.content
                            job.status = "completed"
                            _emit("completed", last.content)

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            _emit("error", str(exc))

    try:
        await asyncio.to_thread(_run)
    except asyncio.CancelledError:
        job._cancel_event.set()  # stop the thread on next chunk boundary
        job.status = "cancelled"
        _emit("cancelled", "Research was cancelled.")
    finally:
        # None is the sentinel that closes the SSE stream
        asyncio.run_coroutine_threadsafe(job.events.put(None), loop)