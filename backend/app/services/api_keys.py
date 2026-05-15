import hashlib
import secrets

from app.core.config import settings


def generate_api_key() -> str:
    token = secrets.token_urlsafe(32)
    return f"{settings.api_key_prefix}_{token}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_display_prefix(api_key: str) -> str:
    return api_key[:16]

