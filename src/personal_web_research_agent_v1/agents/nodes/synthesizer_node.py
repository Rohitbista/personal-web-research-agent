# synthesizer_node.py

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_groq import ChatGroq

from ..state import AgentState
from ..prompts.synthesizer import SYNTHESIZER_SYSTEM_PROMPT
from ...config.settings import GROQ_API_KEY, LLM_MODEL

_synthesizer_llm = ChatGroq(
    model_name=LLM_MODEL, temperature=0.3, groq_api_key=GROQ_API_KEY
)
# NOTE: no .bind_tools() here — and we must never pass tool_call messages to it


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
    print("📝 Synthesising findings...")

    research_context = _messages_to_text(state)

    response = _synthesizer_llm.invoke([
        SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Here is the research gathered:\n\n"
            f"{research_context}\n\n"
            f"Now write the final research report for: {state.get('original_query', '')}"
        )),
    ])

    return {"messages": [AIMessage(content=response.content)]}