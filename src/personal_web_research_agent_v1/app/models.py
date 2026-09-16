from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    session_id: str        # so you can track conversations

class ChatResponse(BaseModel):
    reply: str
    session_id: str