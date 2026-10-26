import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_333_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

SERVICE_CODE = "web-research-agent"
ENV = os.getenv("ENV")
PERSIST_DIR_LOGS = os.getenv("PERSIST_DIR_LOGS")