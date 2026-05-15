import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./agentic_studio.db",
    )
    demo_user_email: str = os.getenv("DEMO_USER_EMAIL", "demo@agentic.studio")
    api_key_prefix: str = os.getenv("API_KEY_PREFIX", "ak_live")
    runtime_base_image: str = os.getenv("RUNTIME_BASE_IMAGE", "agentic-runtime:latest")


settings = Settings()
