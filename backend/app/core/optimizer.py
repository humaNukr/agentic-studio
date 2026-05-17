from typing import List
from app.models.schemas import Message

def optimize_context(messages: List[Message], anchors_count: int = 1, recent_window: int = 4) -> List[Message]:
    """
    Implements the 'Drop Middle' algorithm for context optimization.
    Retains the first 'anchors_count' messages (core instructions)
    and the last 'recent_window' messages (recent steps).
    """
    total_length = len(messages)

    if total_length <= anchors_count + recent_window:
        return messages

    anchors = messages[:anchors_count]
    window = messages[-recent_window:]

    return anchors + window