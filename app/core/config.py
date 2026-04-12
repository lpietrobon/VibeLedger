from pathlib import Path

from pydantic import BaseModel
import os

_default_db_dir = Path.home() / ".vibeledger"
_default_db_url = f"sqlite:///{_default_db_dir / 'vibeledger.db'}"


class Settings(BaseModel):
    app_name: str = "VibeLedger"
    database_url: str = os.getenv("DATABASE_URL", _default_db_url)

    plaid_client_id: str | None = os.getenv("PLAID_CLIENT_ID")
    plaid_secret: str | None = os.getenv("PLAID_SECRET")
    plaid_env: str = os.getenv("PLAID_ENV", "sandbox")
    plaid_products: str = os.getenv("PLAID_PRODUCTS", "transactions")
    plaid_country_codes: str = os.getenv("PLAID_COUNTRY_CODES", "US")
    plaid_redirect_uri: str | None = os.getenv("PLAID_REDIRECT_URI")
    plaid_use_mock: bool = os.getenv("PLAID_USE_MOCK", "false").lower() == "true"

    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    token_encryption_key: str | None = os.getenv("TOKEN_ENCRYPTION_KEY")
    api_token: str | None = os.getenv("VIBELEDGER_API_TOKEN")
    sync_interval_hours: int = int(os.getenv("SYNC_INTERVAL_HOURS", "0"))
    allowed_hosts: str | None = os.getenv("ALLOWED_HOSTS")


settings = Settings()


def validate_security_settings() -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return

    key = settings.token_encryption_key
    if not key:
        raise ValueError("TOKEN_ENCRYPTION_KEY must be set to a valid Fernet key")

    from cryptography.fernet import Fernet
    try:
        Fernet(key.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {e}") from e

    if not settings.api_token:
        raise ValueError("VIBELEDGER_API_TOKEN must be set")
