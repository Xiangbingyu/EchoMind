from agentscope.agent import Agent
from agentscope.state._state import AgentState
from agentscope.tool import Toolkit

from agent_service.runtime.models import build_chat_model


def build_code_agent(*, state: AgentState | None = None) -> Agent:
    return Agent(
        name="CodeAgent",
        system_prompt="You are a code-focused assistant for the EchoMind backend.",
        model=build_chat_model(),
        toolkit=Toolkit(tools=[]),
        state=state,
    )
