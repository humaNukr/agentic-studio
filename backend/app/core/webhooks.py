import httpx
import logging

logger = logging.getLogger(__name__)

async def send_webhook(webhook_url: str, session_id: str, payload: dict):
    """
    Асинхронно відправляє результат роботи агента на сервер клієнта.
    """
    if not webhook_url:
        return

    # Формуємо стандартний контракт (схему), яку очікуватиме клієнт
    data = {
        "session_id": session_id,
        "status": "completed",
        "result": payload
    }

    # Використовуємо AsyncClient для неблокуючого I/O
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=data, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Webhook успішно доставлено на {webhook_url}. Статус: {response.status_code}")
        except httpx.HTTPError as e:
            # Тут логіка retry (повторних спроб) або запис у Dead Letter Queue,
            # але для MVP хакатону достатньо залогувати помилку
            logger.error(f"Помилка доставки webhook на {webhook_url}: {e}")