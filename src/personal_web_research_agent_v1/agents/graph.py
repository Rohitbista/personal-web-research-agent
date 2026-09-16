from langgraph.graph import StateGraph, END

from personal_web_research_agent_v1.agents.state import AgentState
from personal_web_research_agent_v1.agents.nodes import agent_node, tools_node
from personal_web_research_agent_v1.agents.edges import should_continue


# ── Build the graph ──────────────────────────────────────────────────────────
graph = StateGraph(AgentState)

# Register nodes
graph.add_node("agent_node", agent_node)
graph.add_node("tools_node", tools_node)

# Entry point
graph.set_entry_point("agent_node")

# Conditional routing: after the agent responds, decide what to do next
graph.add_conditional_edges(
    "agent_node",
    should_continue,
    {
        "continue": "tools_node",
        "end": END,
    },
)

# After any tool runs, always return to the agent
graph.add_edge("tools_node", "agent_node")

# Compile
app = graph.compile()


# ── Helpers ──────────────────────────────────────────────────────────────────
def print_stream(stream):
    """Pretty-print each message as it streams through the graph."""
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    inputs = {
        "messages": [
            (
                "user",
                "Add 55 and 66 and then multiply the result with 8. "
                "And can you also tell me a joke.",
            )
        ]
    }
    print_stream(app.stream(inputs, stream_mode="values"))