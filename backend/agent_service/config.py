import os
from dotenv import load_dotenv

load_dotenv()

GATEWAY_CALLBACK_URL = os.getenv("GATEWAY_CALLBACK_URL", "http://localhost:8000/internal/callback")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")  # openai | deepseek
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", None)
