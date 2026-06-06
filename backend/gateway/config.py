import os
from dotenv import load_dotenv

load_dotenv()

AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./echomind.db")
