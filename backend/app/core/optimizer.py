from typing import List
from app.models.schemas import Message

def optimize_context(messages: List[Message], anchors_count: int = 1, recent_window: int = 4) -> List[Message]:
    """
    Алгоритм "Drop Middle".
    Залишає 'anchors_count' перших повідомлень (головна задача)
    та 'recent_window' останніх повідомлень (поточні кроки агента).
    Все, що посередині — безжалісно вирізається.
    """
    total_length = len(messages)

    # Якщо історія ще закоротка, щоб її різати — повертаємо як є
    if total_length <= anchors_count + recent_window:
        return messages

    # 1. Зберігаємо якорі (наприклад, найперший промпт юзера, де він описав, що хоче)
    anchors = messages[:anchors_count]

    # 2. Зберігаємо гаряче вікно (наприклад, останні 4 кроки агента)
    window = messages[-recent_window:]

    # 3. Зшиваємо. Середина просто зникає з контексту для LLM
    optimized_messages = anchors + window

    return optimized_messages