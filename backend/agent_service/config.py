import os
from dotenv import load_dotenv

load_dotenv()

GATEWAY_CALLBACK_URL = os.getenv("GATEWAY_CALLBACK_URL", "http://localhost:8000/internal/callback")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # openai | anthropic | ollama
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None)  # 代理地址，留空用官方
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
