from langgraph.prebuilt import ToolNode

from personal_web_research_agent_v1.agents.tools import tools
from personal_web_research_agent_v1.logging.logger_service import LoggerService

logger = LoggerService.get_instance()
_CTX = "src/agents/nodes/tools_node"

# Wrap ToolNode so every tool dispatch is bracketed by log entries.
# ToolNode itself is a callable; we subclass it to intercept __call__.

class _LoggedToolNode(ToolNode):
    def invoke(self, input, config=None, **kwargs):
        # Extract trace_id and messages from input state
        trace_id = input.get("trace_id", "") if isinstance(input, dict) else ""
        messages = input.get("messages", []) if isinstance(input, dict) else []
        last_msg = messages[-1] if messages else None
        tool_calls = getattr(last_msg, "tool_calls", []) or []

        logger.info(
            "Tools node started",
            trace_id=trace_id,
            context=_CTX,
            data={
                "tool_count": len(tool_calls),
                "tools": [tc.get("name") for tc in tool_calls],
            },
        )

        result = super().invoke(input, config=config, **kwargs)

        logger.info(
            "Tools node completed",
            trace_id=trace_id,
            context=_CTX,
            data={"tool_count": len(tool_calls)},
        )

        return result


tools_node = _LoggedToolNode(tools=tools)