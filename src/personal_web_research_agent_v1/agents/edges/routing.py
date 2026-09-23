from ..state import AgentState


def route_after_researcher(state: AgentState) -> str:
    """
    "tools"     → researcher called a tool, keep looping
    "synthesize"→ no tool calls, or iteration cap reached
    """
    last_message = state["messages"][-1]
    at_limit = state.get("iteration_count", 0) >= state.get("max_iterations", 6)

    if at_limit:
        print("⚠️  Iteration limit reached — routing to synthesizer")
        return "synthesize"

    if getattr(last_message, "tool_calls", None):
        return "tools"

    return "synthesize"