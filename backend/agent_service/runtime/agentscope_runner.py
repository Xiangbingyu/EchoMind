from agent_service.agents.code_agent import build_code_agent
from agent_service.runtime.memory import build_agent_state


async def build_runtime_agent(*, history: list[dict]):
    agent_state = build_agent_state(history=history) if history else None
    return build_code_agent(state=agent_state)
