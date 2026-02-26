from pydantic import BaseModel
import os


class Settings(BaseModel):
    app_name: str = "VibeLedger"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./vibeledger.db")

    plaid_client_id: str | None = os.getenv("PLAID_CLIENT_ID")
    plaid_secret: str | None = os.getenv("PLAID_SECRET")
    plaid_env: str = os.getenv("PLAID_ENV", "sandbox")
    plaid_products: str = os.getenv("PLAID_PRODUCTS", "transactions")
    plaid_country_codes: str = os.getenv("PLAID_COUNTRY_CODES", "US")
    plaid_redirect_uri: str | None = os.getenv("PLAID_REDIRECT_URI")
    plaid_use_mock: bool = os.getenv("PLAID_USE_MOCK", "true").lower() == "true"

    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    token_encryption_key: str | None = os.getenv("TOKEN_ENCRYPTION_KEY")
    connect_signing_key: str | None = os.getenv("CONNECT_SIGNING_KEY")


settings = Settings()


def validate_security_settings() -> None:
    # Skip strict key checks during unit tests.
    if os.getenv("PYTEST_CURRENT_TEST"):
        return

    # Enforce key presence/quality at runtime boot.
    if not settings.token_encryption_key or len(settings.token_encryption_key) < 32:
        raise ValueError("TOKEN_ENCRYPTION_KEY must be set to a strong random key")
    if not settings.connect_signing_key or len(settings.connect_signing_key) < 32:
        raise ValueError("CONNECT_SIGNING_KEY must be set to a strong random key")
