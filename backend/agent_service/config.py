import os
from dotenv import load_dotenv

load_dotenv()

GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", "http://localhost:8000").rstrip("/")
GATEWAY_CALLBACK_URL = f"{GATEWAY_BASE_URL}/internal/callback"
GATEWAY_SESSION_URL_TEMPLATE = f"{GATEWAY_BASE_URL}/api/sessions/{{session_id}}"
GATEWAY_MESSAGES_URL_TEMPLATE = f"{GATEWAY_BASE_URL}/api/sessions/{{session_id}}/messages"
GATEWAY_PROJECT_URL_TEMPLATE = f"{GATEWAY_BASE_URL}/api/projects/{{project_id}}"
SESSION_MAX_NON_SYSTEM_MESSAGES = int(os.getenv("SESSION_MAX_NON_SYSTEM_MESSAGES", "12"))

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")  # openai | deepseek
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", None)
