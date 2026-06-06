from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield text tokens one by one."""
