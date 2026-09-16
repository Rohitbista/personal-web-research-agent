from fastapi import FastAPI
import uvicorn

from personal_web_research_agent_v1.app.routes.chat import router

app = FastAPI()

@app.get("/")
def root():
    return {"success":True, "message": "Slack Agent is up and runing"}

app.include_router(router)

def main():
    host = "0.0.0.0"
    port = 8000
    uvicorn.run(
        "personal_web_research_agent_v1.app.server:app",
        host=host,
        port=port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )