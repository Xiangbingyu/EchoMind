from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.state._state import AgentState


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
