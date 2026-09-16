from personal_web_research_agent_v1.agents.state import AgentState

def should_continue(state: AgentState) -> str:
    """
    Routing function that decides whether to call a tool or end the conversation.

    Returns:
        "continue" → route to tools_node (LLM wants to call a tool)
        "end"      → route to END (LLM has a final answer)
    """
    messages = state["messages"]
    last_message = messages[-1]

    if not last_message.tool_calls:
        return "end"
    return "continue"