from personal_web_research_agent_v1.agents.graph import app   # your compiled LangGraph app

# In-memory store — swap for Redis/DB in production
conversation_history: dict[str, list] = {}

def chat(session_id: str, user_message: str) -> str:
    history = conversation_history.get(session_id, [])
    history.append(("user", user_message))

    inputs = {"messages": history}
    config={"recursion_limit": 10}

    last_message = None

    # Stream the execution ONCE
    for chunk in app.stream(inputs, config=config, stream_mode="values"):
        message = chunk["messages"][-1]
        
        # Pretty-print intermediate steps and responses in real-time
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()
            
        last_message = message

    # Extract the final answer from the last message of the completed stream
    ai_reply = last_message.content if last_message else ""
    history.append(("assistant", ai_reply))
    
    conversation_history[session_id] = history
    return ai_reply

# old code without streaming or printing output
    # result = app.invoke(inputs, config={"recursion_limit": 10})   # recursion_limit is for if this gets stuck in a tool execution loop
    
    # # The last message is the agent's final reply
    # ai_reply = result["messages"][-1].content
    # history.append(("assistant", ai_reply))
    # conversation_history[session_id] = history
    # return ai_reply