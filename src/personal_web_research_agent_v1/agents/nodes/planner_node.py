import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

from ..state import AgentState
from ..prompts.planner import PLANNER_SYSTEM_PROMPT
from ...config.settings import GROQ_API_KEY, LLM_MODEL

_planner_llm = ChatGroq(model_name=LLM_MODEL, temperature=0.2, groq_api_key=GROQ_API_KEY)


def planner_node(state: AgentState) -> dict:
    print("🗺️  Planning research queries...")
    original_query = state["messages"][-1].content

    response = _planner_llm.invoke([
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"Research question: {original_query}"),
    ])

    try:
        queries = json.loads(response.content)
        if not isinstance(queries, list):
            raise ValueError
    except (ValueError):
        # Graceful fallback: treat the original question as one query
        queries = [original_query]

    print(f"📋 Sub-queries: {queries}")
    return {
        "original_query": original_query,
        "research_queries": queries,
        "sources": [],
        "iteration_count": 0,
        "max_iterations": 6,
    }