from ..state import AgentState
from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()
_CTX = "src/agents/edges/routing"


def route_after_researcher(state: AgentState) -> str:
    """
    "tools"     → researcher called a tool, keep looping
    "synthesize"→ no tool calls, or iteration cap reached
    """
    trace_id   = state.get("trace_id", "")
    last_message = state["messages"][-1]
    at_limit = state.get("iteration_count", 0) >= state.get("max_iterations", 6)

    if at_limit:
        #print("⚠️  Iteration limit reached — routing to synthesizer")
        logger.info(
            "Routing decision: synthesize (iteration limit reached)",
            trace_id=trace_id,
            context=_CTX,
            data={
                "iteration_count": state.get("iteration_count", 0),
                "max_iterations":  state.get("max_iterations", 6),
                "route":           "synthesize",
            },
        )
        return "synthesize"

    if getattr(last_message, "tool_calls", None):
        tool_names = [tc.get("name") for tc in last_message.tool_calls]
        logger.info(
            "Routing decision: tools",
            trace_id=trace_id,
            context=_CTX,
            data={
                "iteration_count": state.get("iteration_count", 0),
                "tool_calls":      tool_names,
                "route":           "tools",
            },
        )
        return "tools"

    logger.info(
        "Routing decision: synthesize (no tool calls)",
        trace_id=trace_id,
        context=_CTX,
        data={
            "iteration_count": state.get("iteration_count", 0),
            "route":           "synthesize",
        },
    )
    return "synthesize"