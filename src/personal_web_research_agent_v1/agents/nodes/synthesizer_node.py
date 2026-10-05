import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq

from ..state import AgentState
from ..prompts.synthesizer import SYNTHESIZER_SYSTEM_PROMPT
from ...config.settings import GROQ_API_KEY, LLM_MODEL
from personal_web_research_agent_v1.logging.logger_service import LoggerService

_synthesizer_llm = ChatGroq(
    model_name=LLM_MODEL, temperature=0.3, groq_api_key=GROQ_API_KEY
)
# NOTE: no .bind_tools() here — and we must never pass tool_call messages to it

logger = LoggerService.get_instance()
_CTX = "src/agents/nodes/synthesizer_node"


def _messages_to_text(state: AgentState) -> str:
    """
    Flatten the message history into plain text.
    Passing raw AIMessage objects that contain tool_calls to a model with no
    tools bound causes Groq to crash with 'tool_use_failed'.
    """
    lines = []
    for msg in state["messages"]:
        # Handle (role, content) tuples from the initial input
        if isinstance(msg, tuple):
            role, content = msg
            lines.append(f"{role.upper()}: {content}")
            continue

        msg_type = getattr(msg, "type", "")

        if msg_type == "human":
            lines.append(f"USER: {msg.content}")

        elif msg_type == "ai":
            # AIMessages that only contain tool_calls have empty .content — skip them
            if msg.content:
                lines.append(f"RESEARCHER: {msg.content}")

        elif msg_type == "tool":
            # Raw tool results — these are the actual search/fetch payloads
            lines.append(f"TOOL RESULT [{msg.name}]:\n{msg.content}")

    return "\n\n".join(lines)


def synthesizer_node(state: AgentState) -> dict:
    trace_id = state.get("trace_id", "")

    logger.info(
        "Synthesizer node started",
        trace_id=trace_id,
        context=_CTX,
        data={
            "original_query":  state.get("original_query", ""),
            "total_iterations": state.get("iteration_count", 0),
            "sources_count":    len(state.get("sources", [])),
        },
    )

    #print("📝 Synthesising findings...")

    research_context = _messages_to_text(state)
    human_content = (
        f"Here is the research gathered:\n\n"
        f"{research_context}\n\n"
        f"Now write the final research report for: {state.get('original_query', '')}"
    )

    request_payload = {
        "model": LLM_MODEL,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
            {"role": "user",   "content": human_content[:300] + "..."},  # truncate for log
        ],
    }

    start = time.monotonic()
    response = _synthesizer_llm.invoke([
        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ])
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
            "usage": {
                "prompt_tokens":     usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens":      usage.get("total_tokens", 0),
            },
        },
        response_time_ms=str(elapsed_ms),
        trace_id=trace_id,
        message="synthesizer_node LLM call",
    )

    logger.info(
        "Synthesizer node completed",
        trace_id=trace_id,
        context=_CTX,
        data={"response_length": len(response.content)},
    )

    return {"messages": [AIMessage(content=response.content)]}