import json
import time
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

from ..state import AgentState
from ..prompts.planner import PLANNER_SYSTEM_PROMPT
from ...config.settings import GROQ_API_KEY, LLM_MODEL_PLANNER
from ...config.nepal_time import _nepal_now
from personal_web_research_agent_v1.logging.logger_service import LoggerService

_planner_llm = ChatGroq(model_name=LLM_MODEL_PLANNER, temperature=0.2, groq_api_key=GROQ_API_KEY)

logger = LoggerService.get_instance()
_CTX = "src/agents/nodes/planner_node"


def planner_node(state: AgentState) -> dict:
    trace_id = state.get("trace_id", "")

    logger.info(
        "Planner node started",
        trace_id=trace_id,
        context=_CTX,
        data={"original_query": state.get("original_query", "")},
    )

    original_query = state["messages"][-1].content

    system_prompt = PLANNER_SYSTEM_PROMPT.format(
        current_datetime=_nepal_now
    )

    # Build request payload before the call so it can be logged
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research question: {original_query}"),
    ]
    request_payload = {
        "model": LLM_MODEL_PLANNER,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Research question: {original_query}"},
        ],
    }

    start = time.monotonic()
    response = _planner_llm.invoke(messages)
    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    # LangChain AIMessage — metadata lives in response_metadata, not response.usage
    metadata = response.response_metadata
    usage   = metadata.get("token_usage", {})

    logger.log_api_call(
        source="llm",
        status=True,
        request=request_payload,
        response={
            "model":         metadata.get("model_name", LLM_MODEL_PLANNER),
            "finish_reason": metadata.get("finish_reason", ""),
            "usage": {
                "prompt_tokens":     usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens":      usage.get("total_tokens", 0),
            },
        },
        response_time_ms=str(elapsed_ms),
        trace_id=trace_id,
        message="planner_node LLM call",
    )

    try:
        queries = json.loads(response.content)
        if not isinstance(queries, list):
            raise ValueError
    except ValueError:
        queries = [original_query]

    logger.info(
        "Planner node completed",
        trace_id=trace_id,
        context=_CTX,
        data={"query_count": len(queries), "queries": queries},
    )

    return {
        "original_query":   original_query,
        "research_queries": queries,
        "sources":          [],
        "iteration_count":  0,
        "max_iterations":   6,
    }