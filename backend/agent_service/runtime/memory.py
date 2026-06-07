from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.state._state import AgentState


def trim_history(*, history: list[dict], max_non_system_messages: int) -> list[dict]:
    system_messages = [item for item in history if item.get("role") == "system"]
    non_system_messages = [item for item in history if item.get("role") != "system"]
    if max_non_system_messages >= 0:
        non_system_messages = non_system_messages[-max_non_system_messages:]
    return [*system_messages, *non_system_messages]


def build_session_msgs(*, history: list[dict]) -> list:
    messages = []
    for item in history:
        role = item.get("role")
        content = item.get("content", "")
        if role == "system":
            messages.append(SystemMsg("system", content))
        elif role == "user":
            messages.append(UserMsg("user", content))
        elif role == "agent":
            messages.append(AssistantMsg("assistant", content))
    return messages


def build_agent_state(*, history: list[dict]) -> AgentState:
    context = build_session_msgs(history=history)
    summary_lines = [
        "Authoritative session facts from prior conversation:",
    ]
    for item in history:
        role = item.get("role", "unknown")
        content = item.get("content", "")
        summary_lines.append(f"- {role}: {content}")
    summary = "\n".join(summary_lines)
    return AgentState(context=context, summary=summary)
