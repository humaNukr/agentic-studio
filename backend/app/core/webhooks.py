import httpx
import logging

logger = logging.getLogger(__name__)

async def send_webhook(webhook_url: str, session_id: str, payload: dict) -> None:
    """
    Asynchronously delivers the agent's execution result to the client's webhook URL.
    """
    if not webhook_url:
        return

    data = {
        "session_id": session_id,
        "status": "completed",
        "result": payload
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=data, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Webhook delivered successfully to {webhook_url}. Status: {response.status_code}")
        except httpx.HTTPError as e:
            logger.error(f"Failed to deliver webhook to {webhook_url}: {e}")