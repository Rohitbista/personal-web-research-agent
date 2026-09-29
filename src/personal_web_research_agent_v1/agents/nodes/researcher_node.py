import time
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq

from ..state import AgentState
from ..tools import tools
from ..prompts.researcher import RESEARCHER_SYSTEM_PROMPT
from ...config.settings import GROQ_API_KEY, LLM_MODEL
from personal_web_research_agent_v1.logging.logger_service import LoggerService

_researcher_llm = ChatGroq(
    model_name=LLM_MODEL, temperature=0.5, groq_api_key=GROQ_API_KEY
).bind_tools(tools)

logger = LoggerService.get_instance()
_CTX = "src/agents/nodes/researcher_node"


def researcher_node(state: AgentState) -> dict:
    trace_id = state.get("trace_id", "")
    iteration = state.get("iteration_count", 0) + 1

    logger.info(
        "Researcher node started",
        trace_id=trace_id,
        context=_CTX,
        data={
            "iteration": iteration,
            "max_iterations": state.get("max_iterations", 6),
            "original_query": state.get("original_query", ""),
        },
    )

    #print(f"🔍 Researcher iteration {iteration}/{state.get('max_iterations', 6)}")

    system_prompt = RESEARCHER_SYSTEM_PROMPT.format(
        original_query=state.get("original_query", ""),
        research_queries="\n".join(
            f"  - {q}" for q in state.get("research_queries", [])
        ),
    )

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    request_payload = {
        "model": LLM_MODEL,
        "temperature": 0.5,
        "messages": [
            {"role": "system", "content": system_prompt},
            # Subsequent messages are LangChain BaseMessage objects; log count only
            # to avoid serialising tool_call payloads (can be large)
            *[{"role": m.type, "content": str(m.content)[:200]} for m in state["messages"]],
        ],
    }

    start = time.monotonic()
    response = _researcher_llm.invoke(messages)
    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    metadata = response.response_metadata
    usage = metadata.get("token_usage", {})

    logger.log_api_call(
        source="llm",
        status=True,
        request=request_payload,
        response={
            "model":         metadata.get("model_name", LLM_MODEL),
            "finish_reason": metadata.get("finish_reason", ""),
            "tool_calls":    len(getattr(response, "tool_calls", []) or []),
            "usage": {
                "prompt_tokens":     usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens":      usage.get("total_tokens", 0),
            },
        },
        response_time_ms=str(elapsed_ms),
        trace_id=trace_id,
        message="researcher_node LLM call",
    )

    tool_calls = getattr(response, "tool_calls", []) or []
    logger.info(
        "Researcher node completed",
        trace_id=trace_id,
        context=_CTX,
        data={
            "iteration": iteration,
            "tool_calls_requested": len(tool_calls),
            "tool_names": [tc.get("name") for tc in tool_calls],
        },
    )

    return {"messages": [response], "iteration_count": iteration}