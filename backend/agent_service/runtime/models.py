from agentscope.credential import DeepSeekCredential, OpenAICredential
from agentscope.model import DeepSeekChatModel, OpenAIChatModel

from agent_service.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    MODEL_NAME,
    MODEL_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)


def build_openai_chat_model() -> OpenAIChatModel:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required for AgentScope OpenAIChatModel")
    credential = OpenAICredential(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    return OpenAIChatModel(credential=credential, model=MODEL_NAME, stream=True)


def build_deepseek_chat_model() -> DeepSeekChatModel:
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is required for AgentScope DeepSeekChatModel")
    credential = DeepSeekCredential(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return DeepSeekChatModel(credential=credential, model=MODEL_NAME, stream=True)


def build_chat_model():
    if MODEL_PROVIDER == "openai":
        return build_openai_chat_model()
    if MODEL_PROVIDER == "deepseek":
        return build_deepseek_chat_model()
    raise ValueError(f"Unsupported MODEL_PROVIDER: {MODEL_PROVIDER}")
