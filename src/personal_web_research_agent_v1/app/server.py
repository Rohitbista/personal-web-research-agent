from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from personal_web_research_agent_v1.app.routes.research import router as research_router
from personal_web_research_agent_v1.database.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create DB tables on startup (no-op if they already exist)."""
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"success": True, "message": "Web Research Agent is up and running"}


app.include_router(research_router)


def main():
    uvicorn.run(
        "personal_web_research_agent_v1.app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )