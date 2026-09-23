import operator
from typing import Annotated, Sequence, TypedDict, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Preserved so every node knows the original intent
    original_query: str

    # Planned sub-queries from the planner node
    research_queries: List[str]

    # Accumulated source URLs (operator.add lets nodes append overwriting)
    sources: Annotated[List[str], operator.add]

    # Loop guard
    iteration_count: int
    max_iterations: int
