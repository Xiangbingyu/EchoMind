from agentscope.event import EventType


def extract_text_delta(event) -> str:
    if getattr(event, "type", None) != EventType.TEXT_BLOCK_DELTA:
        return ""
    return getattr(event, "delta", "")
