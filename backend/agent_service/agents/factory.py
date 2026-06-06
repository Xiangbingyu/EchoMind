from agent_service.agents.base_provider import LLMProvider
from agent_service.config import LLM_PROVIDER, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


def get_provider() -> LLMProvider:
    if LLM_PROVIDER == "openai":
        from agent_service.agents.openai_provider import OpenAIProvider
        return OpenAIProvider(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")
