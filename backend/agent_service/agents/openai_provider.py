from typing import AsyncIterator
from openai import AsyncOpenAI
from agent_service.agents.base_provider import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None, base_url: str | None = None):
        self._model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        async for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield token
