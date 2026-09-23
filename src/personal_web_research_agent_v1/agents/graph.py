from langgraph.graph import StateGraph, END

from personal_web_research_agent_v1.agents.state import AgentState
from personal_web_research_agent_v1.agents.nodes import planner_node, researcher_node, synthesizer_node, tools_node          # ToolNode unchanged
from personal_web_research_agent_v1.agents.edges.routing import route_after_researcher

graph = StateGraph(AgentState)

graph.add_node("planner_node",     planner_node)
graph.add_node("researcher_node",  researcher_node)
graph.add_node("tools_node",       tools_node)
graph.add_node("synthesizer_node", synthesizer_node)

graph.set_entry_point("planner_node")

graph.add_edge("planner_node", "researcher_node")

graph.add_conditional_edges(
    "researcher_node",
    route_after_researcher,
    {"tools": "tools_node", "synthesize": "synthesizer_node"},
)

graph.add_edge("tools_node",       "researcher_node")
graph.add_edge("synthesizer_node", END)

app = graph.compile()