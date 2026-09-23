from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq

from ..state import AgentState
from ..tools import tools
from ..prompts.researcher import RESEARCHER_SYSTEM_PROMPT
from ...config.settings import GROQ_API_KEY, LLM_MODEL

_researcher_llm = ChatGroq(
    model_name=LLM_MODEL, temperature=0.5, groq_api_key=GROQ_API_KEY
).bind_tools(tools)


def researcher_node(state: AgentState) -> dict:
    iteration = state.get("iteration_count", 0) + 1
    print(f"🔍 Researcher iteration {iteration}/{state.get('max_iterations', 6)}")

    system_prompt = RESEARCHER_SYSTEM_PROMPT.format(
        original_query=state.get("original_query", ""),
        research_queries="\n".join(
            f"  - {q}" for q in state.get("research_queries", [])
        ),
    )

    response = _researcher_llm.invoke(
        [SystemMessage(content=system_prompt)] + list(state["messages"])
    )
    return {"messages": [response], "iteration_count": iteration}