from langgraph.prebuilt import ToolNode

from personal_web_research_agent_v1.agents.tools import tools
from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()
_CTX = "src/agents/nodes/tools_node"

# Wrap ToolNode so every tool dispatch is bracketed by log entries.
# ToolNode itself is a callable; we subclass it to intercept __call__.

class _LoggedToolNode(ToolNode):
    def __call__(self, state, **kwargs):
        trace_id = state.get("trace_id", "")
        last_msg  = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", []) or []

        logger.info(
            "Tools node started",
            trace_id=trace_id,
            context=_CTX,
            data={
                "tool_count": len(tool_calls),
                "tools":      [tc.get("name") for tc in tool_calls],
            },
        )

        result = super().__call__(state, **kwargs)

        logger.info(
            "Tools node completed",
            trace_id=trace_id,
            context=_CTX,
            data={"tool_count": len(tool_calls)},
        )

        return result


tools_node = _LoggedToolNode(tools=tools)