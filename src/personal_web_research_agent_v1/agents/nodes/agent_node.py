from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq

from personal_web_research_agent_v1.agents.state import AgentState
from personal_web_research_agent_v1.agents.tools import tools
from personal_web_research_agent_v1.agents.prompts.agent_node import AGENT_SYSTEM_PROMPT

from personal_web_research_agent_v1.config.settings import GROQ_API_KEY, LLM_MODEL


model = ChatGroq(
    model_name=LLM_MODEL,
    temperature=0.7,
    groq_api_key=GROQ_API_KEY,
).bind_tools(tools)


def agent_node(state: AgentState) -> AgentState:
    print("llm is being called")
    system_prompt = SystemMessage(content=AGENT_SYSTEM_PROMPT)
    response = model.invoke([system_prompt] + state["messages"])
    return {"messages": [response]}