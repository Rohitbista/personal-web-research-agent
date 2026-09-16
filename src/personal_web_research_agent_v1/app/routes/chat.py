from fastapi import APIRouter
from personal_web_research_agent_v1.app.models import ChatRequest, ChatResponse
from personal_web_research_agent_v1.services.chat_service import chat

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    reply = chat(
        session_id=request.session_id,
        user_message=request.message
    )
    return ChatResponse(reply=reply, session_id=request.session_id)