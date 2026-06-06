import os
from dotenv import load_dotenv

load_dotenv()

GATEWAY_CALLBACK_URL = os.getenv("GATEWAY_CALLBACK_URL", "http://localhost:8000/internal/callback")
