from agentscope.event import EventType


def extract_text_delta(event) -> str:
    if getattr(event, "type", None) != EventType.TEXT_BLOCK_DELTA:
        return ""
    return getattr(event, "delta", "")


def build_status_callback(*, session_id: str, status: str) -> dict:
    return {
        "session_id": session_id,
        "type": "task.status",
        "data": status,
    }
